### 📊 FineVision 서브셋별 데이터 규모 통계

FineVision은 총 **24.3M (약 2,430만 건)**의 샘플로 구성되어 있으며, 주요 카테고리별 상세 구성은 다음과 같습니다.

| 카테고리 | 주요 서브셋 (Subset) 예시 | 샘플 건수 (Approx.) | 특징 |
| :--- | :--- | :---: | :--- |
| **Chart & Table** | chartqa, plotqa, dvqa, finqa, tabmwp | **2.4M** | 도표 및 표 기반 시각적 추론 |
| **Document & OCR** | docvqa, rvl_cdip, infographic_vqa, ocrvqa | **2.7M** | 스캔 문서 및 인포그래픽 텍스트 추출 |
| **General VQA** | llava_instruct, sharegpt4v, coco_caption | **4.5M** | 일반 사물 인식 및 자연어 설명 |
| **GUI & Nav** | mind2web, screen_spot, widget_captioning | **1.2M** | 웹/모바일 UI 조작 및 내비게이션 |
| **Text-only** | text_openorca, text_mathinstruct, text_code | **13.5M** | 논리적 사고 및 코딩/수학 추론 (이미지 없음) |
| **기타** | Science, Geometry, Video Frames 등 | **-** | 전문 지식 및 시퀀스 데이터 |

**합계: 약 24,300,000 건 (24.3M)**