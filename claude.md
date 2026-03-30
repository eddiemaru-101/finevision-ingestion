# CLAUDE.md

이 프로젝트는 아래 4개의 문서로 설계가 완료되어 있다.
코드 작성 전 반드시 해당 문서를 참조할 것.

---

## 문서 목록

### 01_assignment.md — 과제 원문
- 과제 출처 및 요구사항 원본
- 구현 목표 (탐색 / 수집 / 다운로드 / 정규화 / 저장) 정의
- 제출물 체크리스트 포함
- 참조 시점: 요구사항이 불명확할 때, 제출 범위 확인할 때

### 02_spec2.md — 구현 명세 (메인 레퍼런스)
- 각 파일(explorer / downloader / normalizer / pipeline / main)의 input/output 타입 정의
- 실제 레코드 구조 (`images`, `texts`, `source`, `metadata`)
- 처리 규칙 (streaming, 배치, 체크포인트, 에러 격리) 상세 명세
- 참조 시점: 코드 작성할 때 항상 열어둘 것

### 03_datastructure.md — 데이터 구조 분석
- HuggingFace에서 실제로 내려오는 레코드 필드 목록 및 타입
- `record_id` 생성 방식 (SHA256), `metadata` Schema-on-Read 결정 배경
- 중복 제거 기준 (`image_path + question`) 결정 근거
- 참조 시점: 필드 타입이나 설계 결정의 이유가 궁금할 때

### 04_plan.md — 최종 설계서
- Hybrid Flattening 전략 (N×M row 펼치기) 설명
- 출력 스키마 테이블 (record_id / uid / subset / split / source / image_path / question / answer / metadata)
- 이미지 파일명 명명 규칙 (`{record_id}_{image_index}.jpg`)
- 체크포인트 / 배치 커밋 / 에러 격리 설계 요약
- 참조 시점: 전체 구조를 한눈에 파악할 때, 설계 의도 확인할 때

---

## 핵심 제약 (모든 파일 공통)

- `streaming=True` 필수 — `load_dataset` 전체 로드 금지
- `trust_remote_code` 사용 금지
- 이미지 없는 레코드 → `image_path=""` 로 저장 (skip 아님)
- 중복 row → skip (`image_path + question` 조합 기준)
- 에러 레코드 → `./data/failed_records.jsonl` 기록 후 파이프라인 계속 진행
- `record_id` → uuid4 금지, SHA256 해시 사용