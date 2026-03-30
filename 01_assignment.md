# FineVision 데이터 수집 파이프라인 - 과제 요약

## 데이터셋

- 출처: `HuggingFaceM4/FineVision`
- 구성: 여러 subset(aokvqa, chart2text, docvqa, screenqa 등) × split(train, validation, test)
- 총 용량: 약 4.4TB

---

## 구현 목표

### 1. 자동 탐색
- 하드코딩 없이 전체 subset / split 조합을 코드로 탐색
- 모든 조합을 순회

### 2. 데이터 수집 (streaming)
- `datasets` 라이브러리의 `streaming=True` 사용
- 각 레코드에서 메타데이터 추출 → 다음 단계로 전달
  - 추출 필드: `image`, `question`, `answer`, `subset`, `split`

### 3. 이미지 다운로드
- 이미지 URI 또는 binary field 사용해서 로컬 저장
- 권장 저장 구조:
  ```
  ./data/{subset}/{split}/{filename}.jpg
  ```
  예: `./data/aokvqa/train/xxx.jpg`

### 4. 데이터 정규화 및 저장
- 공통 스키마로 통합:
  ```
  subset | split | uid | image_path | question | answer
  ```
- 중복 기준 정의 후 제거 (예: `image_path + question`)
- 저장 포맷: SQLite DB 또는 Parquet

---

## 제약 조건

- 4.4TB 전체 저장 불가 시 → 최대 개수/용량 제한 또는 샘플링 방식 허용
- 다운로드 경로는 항상 로컬 디렉토리 기준

---

## 제출물 체크리스트

- [ ] 코드 압축 파일
- [ ] 전체 설계 요약
- [ ] 실행 방법 및 의존성
- [ ] 샘플 실행 결과

---

## 구현할 파일 구조

```
finevision-ingestion/
├── src/
│   ├── __init__.py
│   ├── explorer.py      # subset/split 자동 탐색
│   ├── downloader.py    # 이미지 다운로드
│   ├── normalizer.py    # 공통 스키마 변환 + 중복 제거
│   └── pipeline.py      # 전체 파이프라인 조합
├── data/                # 다운로드된 이미지 저장
├── pyproject.toml
├── main.py              # 진입점
└── README.md
```