import json
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from datasets import load_dataset
from tqdm import tqdm

from .downloader import save_images
from .explorer import DATASET_NAME, get_all_subsets_and_splits
from .normalizer import make_record_id, normalize

CHECKPOINT_PATH = Path("data/logs/checkpoint.json")
OUTPUT_PATH = Path("data/output.parquet")
FAILED_PATH = Path("data/failed/failed_records.jsonl")
RUN_LOG_PATH = Path("data/logs/run_log.jsonl")
BATCH_SIZE = 1000  # 배치 커밋 단위


def load_checkpoint() -> set[str]:
    """
    checkpoint.json에서 완료된 subset/split 목록을 읽어온다.
    파일이 없으면 빈 set 반환.
    """
    if CHECKPOINT_PATH.exists():
        data = json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
        return set(data.get("completed", []))
    return set()


def save_checkpoint(completed: set[str]) -> None:
    """
    완료된 subset/split 목록을 checkpoint.json에 기록한다.
    재시작 시 이 파일을 읽어 완료된 조합은 load_dataset 호출 자체를 건너뜀.
    """
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_PATH.write_text(
        json.dumps({"completed": sorted(completed)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _now() -> str:
    """현재 시각을 ISO 8601 형식으로 반환한다."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log_run(entry: dict) -> None:
    """
    실행 통계를 run_log.jsonl에 한 줄씩 append한다.
    덮어쓰지 않고 누적되므로 여러 번 실행해도 기록이 쌓인다.
    """
    RUN_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RUN_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def log_failed(record_info: dict, error: str) -> None:
    """
    파싱/다운로드/저장 실패 레코드를 failed_records.jsonl에 기록한다.
    파이프라인은 이 레코드를 건너뛰고 계속 진행한다.
    """
    FAILED_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(FAILED_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps({**record_info, "error": error}, ensure_ascii=False) + "\n")


def run(max_samples: int = 100) -> None:
    """
    전체 파이프라인 실행.

    처리 흐름:
    1. explorer로 전체 subset/split 목록 탐색
    2. 완료된 조합은 checkpoint로 건너뜀
    3. 각 조합을 streaming=True로 로드 (전체 로드 금지)
    4. 레코드마다:
       a. make_record_id로 SHA256 record_id 생성
       b. downloader로 이미지 저장 → image_paths 반환
       c. normalizer로 N×M 펼치기 → row 리스트 반환
    5. 배치 1000개 단위로 Parquet에 append 저장
    6. subset/split 완료 시 checkpoint 기록
    7. 마지막 남은 배치 저장
    """
    subsets_splits = get_all_subsets_and_splits()
    completed = load_checkpoint()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    pipeline_start = time.time()
    run_started_at = _now()
    total_records = 0  # 전체 처리 레코드 수 (중복/에러 포함)

    # ParquetWriter를 열어두고 전체 파이프라인 동안 append 방식으로 쓴다.
    # 스키마는 첫 번째 배치에서 자동 결정됨.
    writer: pq.ParquetWriter | None = None
    batch: list[dict] = []

    try:
        for item in subsets_splits:
            subset = item["subset"]
            split = item["split"]
            key = f"{subset}/{split}"

            # 이미 완료된 subset/split은 load_dataset 호출 자체를 건너뜀
            if key in completed:
                print(f"[pipeline] skip (완료됨): {key}")
                continue

            print(f"[pipeline] 처리 시작: {key}")
            subset_start = time.time()

            try:
                # streaming=True 필수 — 4.4TB 전체 로드 금지
                # trust_remote_code 사용 금지 (FineVision은 표준 Parquet 포맷)
                dataset = load_dataset(
                    DATASET_NAME,
                    name=subset,
                    split=split,
                    streaming=True,
                )
            except Exception as e:
                print(f"[pipeline] load_dataset 실패: {key} — {e}")
                log_failed({"subset": subset, "split": split}, str(e))
                continue

            count = 0
            for record in tqdm(dataset, desc=key, total=max_samples):
                if count >= max_samples:
                    break

                try:
                    # 1. SHA256으로 원본 레코드 식별자 생성
                    record_id = make_record_id(record)

                    # 2. 이미지 저장 → 경로 리스트 반환 (없으면 빈 리스트)
                    image_paths = save_images(record, subset, split, record_id)

                    # 3. N×M 펼치기 + 중복 제거 → row 리스트 반환
                    rows = normalize(record, image_paths, subset, split, record_id)
                    batch.extend(rows)

                except Exception:
                    # 에러 레코드 기록 후 파이프라인 계속 진행
                    log_failed(
                        {"subset": subset, "split": split},
                        traceback.format_exc(),
                    )

                # 배치가 차면 Parquet에 flush 후 초기화
                if len(batch) >= BATCH_SIZE:
                    writer = _write_batch(batch, writer)
                    batch.clear()

                count += 1

            # subset/split 단위 완료 기록 (재시작 시 이 조합은 건너뜀)
            completed.add(key)
            save_checkpoint(completed)
            total_records += count

            subset_elapsed = time.time() - subset_start
            speed = count / subset_elapsed if subset_elapsed > 0 else 0

            # 남은 조합 수 기준으로 전체 예상 시간 계산
            remaining = len(subsets_splits) - len(completed)
            eta_sec = (subset_elapsed * remaining) if remaining > 0 else 0
            eta_str = _fmt_seconds(eta_sec)

            print(
                f"[pipeline] 완료: {key} | "
                f"{count}건 | "
                f"소요: {_fmt_seconds(subset_elapsed)} | "
                f"속도: {speed:.1f}건/s | "
                f"남은 조합: {remaining}개 | "
                f"예상 잔여: {eta_str}"
            )
            log_run({
                "type": "subset",
                "subset_split": key,
                "records": count,
                "elapsed_sec": round(subset_elapsed, 2),
                "speed_per_sec": round(speed, 2),
                "timestamp": _now(),
            })

    finally:
        # 마지막 남은 배치 저장
        if batch:
            writer = _write_batch(batch, writer)

        # ParquetWriter 닫기
        if writer is not None:
            writer.close()

    total_elapsed = time.time() - pipeline_start
    print(
        f"[pipeline] 전체 완료 | "
        f"총 소요: {_fmt_seconds(total_elapsed)} | "
        f"총 처리: {total_records}건 | "
        f"출력: {OUTPUT_PATH}"
    )
    log_run({
        "type": "total",
        "started_at": run_started_at,
        "finished_at": _now(),
        "total_records": total_records,
        "elapsed_sec": round(total_elapsed, 2),
        "max_samples": max_samples,
    })


def _fmt_seconds(sec: float) -> str:
    """초를 'Xh Ym Zs' 형식으로 변환한다."""
    sec = int(sec)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m}m {s}s"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


def _write_batch(batch: list[dict], writer: pq.ParquetWriter | None) -> pq.ParquetWriter:
    """
    배치를 PyArrow Table로 변환해 ParquetWriter로 쓴다.
    writer가 None이면 새로 생성한다 (첫 번째 배치에서 스키마 자동 결정).
    """
    table = pa.Table.from_pylist(batch)

    if writer is None:
        # 첫 배치: 스키마 확정 후 writer 생성
        writer = pq.ParquetWriter(str(OUTPUT_PATH), schema=table.schema)

    writer.write_table(table)
    return writer
