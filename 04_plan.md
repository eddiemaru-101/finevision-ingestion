# 🏗️ FineVision 데이터 수집 파이프라인 설계서 (Final Spec)

본 설계는 **4.4TB** 규모의 거대 데이터셋을 안정적으로 처리하기 위해 **Hybrid Flattening**과 **Schema-on-Read** 전략을 채택합니다.

---

### 1. 데이터 저장 및 스키마 전략: **Hybrid Flattening**
모든 데이터를 하나의 틀에 강제하지 않고, 검색용 고정 필드와 유연한 상세 필드를 분리하여 저장합니다.

| 구분 | 필드명 | 데이터 타입 | 비고 (작동 방식) |
| :--- | :--- | :--- | :--- |
| **식별자** | `record_id` | String (Hash) | `images[0] + texts[0]` 해시값. 재시작 시 일관성 유지 용도. |
| **식별자** | `uid` | String (UUID) | 펼쳐진(Flattened) 각 행(Row)의 고유 키. |
| **고정 필드** | `subset`, `split`, `source` | String | 데이터 계보(Lineage) 추적 및 필터링용. |
| **이미지** | `image_path` | String | 로컬에 저장된 이미지 파일의 상대 경로. |
| **텍스트** | `question`, `answer` | String | `texts` 리스트 내 `user`, `assistant` 값을 1:1 매핑. |
| **가변 필드** | `metadata` | JSON String | **Schema-on-Read** 적용. 서브셋별 품질 점수 등 부가 정보 보존. |

---

### 2. 핵심 처리 로직
대규모 멀티모달 데이터의 특성을 고려한 처리 규칙입니다.

* **N × M Flattening (데이터 펼치기)**:
    - 한 레코드 내 이미지 $N$개, 질문-답변 쌍 $M$개가 있을 때 $N \times M$개의 행으로 생성합니다.
    - 예: 이미지 2장, Q-A 2쌍 → 총 4개의 독립적인 Row 저장.
* **이미지 부재 처리**:
    - `images`가 빈 리스트인 경우에도 레코드를 버리지 않고 `image_path`를 `""`로 기록하여 저장합니다.
* **중복 제거 (Deduplication)**:
    - `image_path + question` 조합을 기준으로 중복 여부를 판단하여 중복 시 해당 행은 Skip합니다.

---

### 3. 체크포인트 및 안정성 설계
장애 발생 시 자원 낭비를 막기 위한 실무형 장치입니다.

* **Subset 단위 체크포인트 (checkpoint.json)**:
    - 각 `subset/split` 처리가 완료될 때마다 상태를 기록합니다.
    - **재시작 시**: 완료된 조합은 데이터 로드 단계부터 건너뛰어 중복 연산을 방지합니다.
* **배치 커밋 (Batch Commit)**:
    - 1,000개 단위로 메모리에 적재한 후 **Parquet** 파일에 Append 방식으로 저장합니다.
* **에러 격리 (failed_records.jsonl)**:
    - 파싱이나 다운로드 실패 시 해당 레코드 정보와 에러 메시지를 기록하고 파이프라인은 중단 없이 계속 진행합니다.

---

### 4. 권장 파일 구조

```text
finevision-ingestion/
├── src/
│   ├── explorer.py      # datasets API를 사용한 동적 subset/split 탐색
│   ├── downloader.py    # PIL.Image.save() 기반 로컬 디렉토리 저장
│   ├── normalizer.py    # N×M Flattening 및 중복 필터링 로직
│   └── pipeline.py      # Streaming 로드 및 배치 저장 프로세스 제어
├── data/
│   ├── {subset}/{split}/ # 이미지 바이너리 저장소
│   ├── checkpoint.json  # 진행 상태 기록 (Resume용)
│   └── output.parquet   # 최종 정규화된 통합 데이터셋
└── main.py              # CLI 진입점 (--max-samples 파라미터 제어)
```

---

### 5. 이미지 파일명 명명 규칙 (Naming Convention)
이미지 저장 시 유일성을 보장하고 원본 레코드와의 역추적을 용이하게 하기 위해 다음과 같은 규칙을 적용합니다.

* **파일명 구조**: `{record_id}_{image_index}.jpg`
* **구성 요소 상세**:
    - **`record_id`**: 원본 레코드를 식별하는 고정 해시값입니다.
        - 생성 방식: `첫 번째 이미지의 바이트 데이터 + 첫 번째 질문 텍스트`를 조합하여 SHA256 해시 생성.
        - 목적: `uuid4`와 달리 동일한 원본 데이터에 대해 항상 같은 ID를 생성하므로, 파이프라인 재시작 시 데이터 일관성을 유지합니다.

    - **`image_index`**: 단일 레코드 내에 포함된 이미지 리스트에서의 순번(0부터 시작)입니다.
        - 목적: 하나의 레코드에 여러 장의 이미지가 포함된 경우(N개), 각 이미지를 고유하게 구분합니다.

* **저장 규칙**:
    - **디렉토리 분리**: 한 폴더에 너무 많은 파일이 쌓이는 것을 방지하기 위해 `./data/{subset}/{split}/` 구조를 엄격히 준수합니다.
    - **포맷 통일**: 원본 형식과 관계없이 학습 라이브러리와의 호환성이 가장 좋은 `.jpg` 확장자로 통일하여 저장합니다.
    - **이미지 부재 시**: `images` 필드가 비어있는 경우 파일 생성을 건너뛰고 DB의 `image_path` 컬럼값만 `""`로 처리합니다.








