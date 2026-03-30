# FineVision 데이터 구조 파악 및 설계 결정사항

## 1. 데이터셋 구성

- 총 subset 수: 185개
- 확인한 subset: `CoSyn_400k_chart`
- split: `train` 1개 (subset마다 다를 수 있음)

---

## 2. 실제 레코드 구조 (CoSyn_400k_chart 기준)

| # | 필드 | 타입 | 의미 |
|---|------|------|------|
| 1 | `images` | list[PIL.Image] | 실제 이미지 (1개 이상) |
| 2 | `texts` | list[dict] | 질문-답변 쌍 (1개 이상) — `{"user": "질문", "assistant": "답변"}` |
| 3 | `source` | str | 원본 데이터셋 출처 |
| 4 | `relevance_ratings` | list[int] | 이미지-질문 관련성 점수 (평가자 10명, 1~5점) |
| 5 | `relevance_min` | int | relevance_ratings 최솟값 |
| 6 | `visual_dependency_ratings` | list[int] | 질문 답변에 이미지가 반드시 필요한 정도 (1~5점) |
| 7 | `visual_dependency_min` | int | visual_dependency_ratings 최솟값 |
| 8 | `image_correspondence_ratings` | list[int] | 답변 내용이 이미지와 일치하는 정도 (1~5점) |
| 9 | `image_correspondence_min` | int | image_correspondence_ratings 최솟값 |
| 10 | `formatting_ratings` | list[int] | 답변 형식 품질 (1~5점) |
| 11 | `formatting_min` | int | formatting_ratings 최솟값 |

---

## 3. 이미지 형태

- `PIL.PngImagePlugin.PngImageFile` 객체 — PIL.Image의 하위 클래스
- HuggingFace `datasets` 라이브러리가 스트리밍 시점에 이미 PIL.Image로 변환해서 넘겨줌
- 별도 디코딩 불필요, `.save()`로 바로 저장 가능

---

## 4. 논문 기반 확인사항 (FineVision 논문)

FineVision 논문에 따르면 모든 subset이 아래 공통 스키마로 이미 정규화되어 있음.

```
sample = {images, texts, source, metadata}
```

- 200개 이상의 원본 데이터셋을 FineVision 제작팀이 이미 공통 스키마로 변환해서 저장해놓은 것
- 즉 **모든 subset의 최상위 필드 구조는 동일** — subset마다 필드가 다를 것이라는 우려 해소
- 이미지 없는 subset도 `images` 필드는 존재하되 빈 리스트 `[]`일 가능성 높음
- `metadata` 필드에 품질 평가 점수(`relevance_min` 등) 및 태스크별 추가 정보 포함

---

## 5. 주의사항

- `image` 필드 없음 → `images` 리스트
- `question`/`answer` 필드 없음 → `texts` 리스트 안의 `user`/`assistant`
- `trust_remote_code` 사용 금지 — FineVision이 표준 Parquet 포맷으로 전환됨
- 모든 subset 공통 필드: `images`, `texts`, `source`, `metadata`

---

## 5. 설계 결정사항

### 스키마 정규화 방식

레코드 1개에 이미지 N개, 질문-답변 쌍 M개가 들어올 수 있음.
이미지 × 질문-답변 쌍 조합으로 펼쳐서 row 여러 개로 저장.

- Q-A 쌍은 `{"user", "assistant"}` dict 단위로 유지 — 쌍을 쪼개지 않음
- 이미지 1개 × 질문-답변 쌍 1개 = row 1개

예시: images=[img_0, img_1], texts=[qa_0, qa_1] → 4개 row

```
uid     | image_path | question | answer
abc-123 | img_0.jpg  | Q1       | A1
abc-124 | img_0.jpg  | Q2       | A2
abc-125 | img_1.jpg  | Q1       | A1
abc-126 | img_1.jpg  | Q2       | A2
```

### 공통 스키마

```
subset | split | uid | image_path | question | answer | source
| relevance_min | visual_dependency_min
| image_correspondence_min | formatting_min
```

### 중복 기준

`image_path` + `question` 두 값의 조합이 동일하면 중복으로 판단하고 skip.

### 저장 포맷

Parquet 우선 (`./data/output.parquet`) — 스키마 선언 불필요, 배치 쓰기 최적화.

### 이미지 저장 경로

```
./data/{subset}/{split}/{uid}_{index}.jpg
```

### 이미지 없는 레코드

`images` 필드 없거나 빈 리스트면 `image_path`를 `""`으로 저장 — skip 아님.

### 체크포인트

subset/split 하나 완료될 때마다 `./data/checkpoint.json`에 기록.
재시작 시 완료된 subset/split은 `load_dataset` 호출 자체를 skip.

### 에러 처리

파싱 실패 레코드는 `./data/failed_records.jsonl`에 기록하고 파이프라인 계속 진행.


### source 필드 특성

- `source`는 데이터셋 이름표일 뿐 — 같은 데이터셋의 수천~수만 레코드가 동일한 값을 가짐
- `source` 단독으로는 개별 레코드 식별 불가
- 서로 다른 `source` 간에도 동일한 이미지+질문 조합이 존재할 수 있음 (교차 중복)

예시:
```
레코드 A: source="chartqa",          image=B, question="Q2"  → 중복
레코드 B: source="CoSyn_400k_chart", image=B, question="Q2"  → 중복
```

---

### 공통 스키마
```
record_id | subset | split | uid | image_path | question | answer | source | metadata
```

- `record_id`: 원본 레코드 단위 식별자 — 같은 레코드에서 파생된 row들을 묶어주는 키
- `uid`: 펼친 row 각각의 고유 식별자
- `source`: 원본 데이터셋 이름 (예: "chartqa", "CoSyn-400k-chart")
- `metadata`: subset마다 내용이 다르므로 JSON 문자열로 통째로 저장

---

### record_id 생성 방식

uuid4 사용 금지 — 재시작 시 같은 원본 레코드에 다른 ID가 붙음.
`images[0]의 바이트 + texts[0]["user"]` 조합을 SHA256으로 해시해서 생성.
재시작해도 동일한 원본 레코드에 동일한 ID가 보장됨.

### metadata 저장 방식 (Schema-on-Read)

subset마다 `metadata` 내부 구조가 다름. 저장 시점에 전체 구조를 알 수 없으므로 JSON 문자열로 통째로 저장.

- 자주 쿼리할 핵심 필드(`question`, `answer`, `image_path` 등)는 개별 컬럼으로 분리
- `metadata`는 subset마다 구조가 다르고 현재 쿼리 대상이 아니므로 JSON 문자열 컬럼 하나에 보존
- 나중에 특정 필드가 필요해지면 그때 `metadata` 컬럼에서 뽑아서 쓰면 됨 — 저장 시점에 미리 알 필요 없음

이 방식을 Schema-on-Read라고 함.
저장할 때는 구조 정의 없이 raw 데이터 보존, 읽을 때 필요한 구조로 해석.