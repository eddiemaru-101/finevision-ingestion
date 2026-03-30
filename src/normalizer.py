import hashlib
import io
import json
import uuid
from itertools import product


def make_record_id(record: dict) -> str:
    """
    원본 레코드의 고유 식별자를 SHA256으로 생성한다.

    - uuid4 사용 금지: 재시작 시 동일한 원본 레코드에 다른 ID가 붙는 문제 방지
    - 생성 기준: images[0]의 바이트 데이터 + texts[0]["user"] 텍스트 조합
    - images가 없으면 texts[0]["user"]만 사용
    - 동일한 원본 → 항상 동일한 record_id 보장 (파이프라인 재시작 시 일관성 유지)
    """
    images = record.get("images") or []
    texts = record.get("texts") or []

    first_text = texts[0]["user"] if texts else ""

    if images:
        first_img = images[0]
        if isinstance(first_img, bytes):
            img_bytes = first_img
        else:
            # PIL.Image 객체 → 바이트로 변환
            buf = io.BytesIO()
            first_img.save(buf, format="PNG")
            img_bytes = buf.getvalue()
        raw = img_bytes + first_text.encode("utf-8")
    else:
        raw = first_text.encode("utf-8")

    return hashlib.sha256(raw).hexdigest()


def normalize(
    record: dict,
    image_paths: list[str],
    subset: str,
    split: str,
    record_id: str,
) -> list[dict]:
    """
    레코드 1개를 N×M 방식으로 펼쳐서 row 리스트로 반환한다.

    N×M Flattening:
    - N = 이미지 수 (없으면 image_path="" 로 row 1개 생성 — 레코드 버리지 않음)
    - M = texts(질문-답변 쌍) 수 (없으면 question/answer="" 로 row 1개 생성)
    - 예: images 2개 × QA 2쌍 → 4개 row

    중복 제거:
    - 기준: image_path + question 조합
    - 같은 조합이 이미 있으면 해당 row만 skip

    metadata (Schema-on-Read):
    - subset마다 내부 구조가 다를 수 있으므로 저장 시점에 구조 정의 없이 JSON 문자열로 보존
    - 나중에 필요한 필드가 생기면 그때 metadata 컬럼에서 뽑아 쓰면 됨
    """
    texts = record.get("texts") or []
    source = record.get("source") or ""

    # images / texts / source 제외한 나머지 필드 전체를 metadata JSON으로 보존
    meta_fields = {
        k: v for k, v in record.items()
        if k not in ("images", "texts", "source")
    }
    metadata_str = json.dumps(meta_fields, ensure_ascii=False, default=str)

    # 이미지 없으면 [""] 한 개로 처리 — 이미지 없는 레코드도 row를 생성해야 함
    img_list = image_paths if image_paths else [""]

    # 질문-답변 쌍 없으면 빈 쌍 한 개로 처리
    qa_list = texts if texts else [{"user": "", "assistant": ""}]

    rows = []
    seen: set[str] = set()  # 레코드 내 중복 체크 (image_path + question)

    for img_path, qa in product(img_list, qa_list):
        question = qa.get("user", "") if isinstance(qa, dict) else ""
        answer = qa.get("assistant", "") if isinstance(qa, dict) else ""

        # 중복 row skip
        dedup_key = img_path + question
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        rows.append({
            "record_id": record_id,       # 원본 레코드 식별자 (SHA256, 재시작 일관성)
            "uid": str(uuid.uuid4()),      # 펼친 row 각각의 고유 식별자 (uuid4)
            "subset": subset,
            "split": split,
            "source": source,
            "image_path": img_path,
            "question": question,
            "answer": answer,
            "metadata": metadata_str,      # 품질 점수 등 부가 정보 (JSON 문자열)
        })

    return rows
