# FineVision Ingestion Pipeline - Implementation Spec

## 프로젝트 목표

HuggingFace `HuggingFaceM4/FineVision` 데이터셋의 모든 subset/split을 자동 탐색하고,
이미지를 로컬에 저장한 뒤, 공통 스키마로 정규화하여 Parquet 또는 SQLite로 저장하는 단일 파이프라인 구축.

---

## 환경

- Python 3.11
- 패키지 관리: uv
- 설치된 패키지: datasets, pillow, tqdm
- 로컬 경로: `~/finevision-dataset/finevision-ingestion`
- 저장 경로: `./data/{subset}/{split}/{filename}.jpg`

---

## 파일 구조 및 각 파일의 역할

```
finevision-ingestion/
├── src/
│   ├── __init__.py
│   ├── explorer.py      # subset/split 목록 탐색
│   ├── downloader.py    # 이미지 저장
│   ├── normalizer.py    # 공통 스키마 변환 + 중복 제거
│   ├── pipeline.py      # explorer → downloader → normalizer 순서로 조합
│   └── main.py          # CLI 진입점, 파라미터 수신
├── data/
├── pyproject.toml
└── README.md
```

---

## 각 파일 명세

### explorer.py

- **역할**: HuggingFace API를 사용해 FineVision의 전체 subset 목록과 각 subset의 split 목록을 반환
- **하드코딩 금지**: subset 이름, split 이름 모두 코드로 동적 탐색
- **input**: 없음
- **output**: `list[dict]` — `[{"subset": "aokvqa", "split": "train"}, ...]`
- **사용 API**: `datasets.get_dataset_config_names()`, `datasets.get_dataset_split_names()`

### downloader.py

- **역할**: 단일 레코드에서 이미지 리스트를 추출해 로컬에 저장
- **input**: 레코드 dict, subset명, split명, uid(string)
  - 실제 레코드 구조:
    - `images`: list[PIL.Image] — 이미지 1개 이상
    - `texts`: list[dict] — `{"user": "질문", "assistant": "답변"}` 1쌍 이상
    - `source`: str — 원본 데이터셋 출처
    - `relevance_min`, `visual_dependency_min`, `image_correspondence_min`, `formatting_min`: int — 품질 평가 최솟값
- **output**: 저장된 이미지 경로 리스트 `list[str]` — 이미지 없으면 빈 리스트 반환
- **저장 경로 규칙**: `./data/{subset}/{split}/{uid}_{index}.jpg`
  - 이미지 여러 개면 index로 구분: `uid_0.jpg`, `uid_1.jpg`
- **처리 규칙**:
  - `images` 필드 없거나 빈 리스트면 빈 리스트 반환 (에러 발생 금지)
  - PIL.Image이면 `.save()` 사용
  - bytes이면 `io.BytesIO`로 변환 후 저장

### normalizer.py

- **역할**: 레코드를 공통 스키마 dict 리스트로 변환하고, 중복 제거
- **input**: 레코드 dict + image_paths(list[str]) + subset(string) + split(string) + uid(string)
- **output**: 정규화된 dict 리스트 — 이미지 × 질문-답변 쌍의 모든 조합을 1:1로 펼침
  ```
  [
    {
      "subset": str,
      "split": str,
      "uid": str,           # uuid4로 생성
      "image_path": str,    # 이미지 경로 1개
      "question": str,      # texts[n]["user"]
      "answer": str,        # texts[n]["assistant"]
      "source": str,        # 원본 데이터셋 출처
      "relevance_min": int,
      "visual_dependency_min": int,
      "image_correspondence_min": int,
      "formatting_min": int
    },
    ...
  ]
  ```
- **펼치는 방식**: 이미지 리스트 × texts 리스트를 조합
  - images=[img_0, img_1], texts=[qa_0, qa_1] → 4개 row 생성
- **중복 기준**: `image_path` + `question` 두 값의 조합이 동일하면 중복
- **중복 처리**: 중복 row는 저장하지 않고 skip
- **필드 없을 때 처리**:
  - `texts` 없거나 빈 리스트면 question/answer 모두 `""` (빈 문자열)
  - `images` 없거나 빈 리스트면 image_path `""`

### pipeline.py

- **역할**: explorer → downloader → normalizer를 순서대로 조합해서 전체 파이프라인 실행
- **streaming 방식**: `datasets.load_dataset(..., streaming=True)` 사용, 전체 로드 금지
- **주의**: `trust_remote_code` 사용 금지 — FineVision은 표준 Parquet 포맷으로 전환됨
- **input**: `max_samples` (int, 기본값 100) — subset/split 조합당 최대 레코드 수
- **처리 흐름**:
  1. explorer로 전체 subset/split 목록 가져옴
  2. 각 조합에 대해 streaming으로 데이터 로드
  3. 레코드마다 uuid4로 uid 생성
  4. downloader로 이미지 저장 → image_paths 반환
  5. normalizer로 이미지 × 질문-답변 조합 펼쳐서 row 리스트 반환
  6. 결과를 배치로 누적 (1000개 단위)
  7. 배치가 차면 Parquet에 append로 저장, 배치 초기화
  8. 모든 subset/split 완료 후 남은 배치 저장
- **저장 포맷**: Parquet 우선 (`./data/output.parquet`), SQLite는 옵션
- **체크포인트**: subset/split 하나 완료될 때마다 `./data/checkpoint.json`에 기록
  ```
  {"completed": ["CoSyn_400k_chart/train", "aokvqa/train", ...]}
  ```
- **재시작 시**: checkpoint 읽어서 완료된 subset/split은 `load_dataset` 호출 자체를 skip

### main.py

- **역할**: CLI 진입점
- **파라미터**:
  - `--max-samples` (int, 기본값 100): subset/split 조합당 최대 수집 레코드 수
  - `--output-format` (str, 기본값 "parquet"): "parquet" 또는 "sqlite"
- **실행 방법**: `uv run python src/main.py --max-samples 10`

---

## 전체 처리 흐름

```
main.py
  └─ pipeline.py
       ├─ explorer.py        → subset/split 목록 반환
       ├─ load_dataset(streaming=True)
       ├─ downloader.py      → 이미지 저장 → image_path 반환
       ├─ normalizer.py      → 공통 스키마 dict 반환
       └─ parquet / sqlite 저장
```

---

## 제약 조건

- 전체 데이터셋 4.4TB → `max_samples`로 반드시 수집량 제한
- `streaming=True` 필수, `load_dataset` 전체 로드 금지
- `trust_remote_code` 사용 금지
- 이미지 없는 레코드는 image_path `""` 로 저장 (skip 아님)
- 중복 row는 저장하지 않고 skip (`image_path` + `question` 조합 기준)
- 배치 1000개 단위로 Parquet append 저장
- 에러 발생 레코드는 `./data/failed_records.jsonl`에 기록하고 파이프라인 계속 진행

---

## 제출물 체크리스트

- [ ] 코드 압축 파일
- [ ] 전체 설계 요약
- [ ] 실행 방법 및 의존성
- [ ] 샘플 실행 결과