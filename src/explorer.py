from datasets import get_dataset_config_names, get_dataset_split_names

# 대상 데이터셋 (HuggingFace Hub)
DATASET_NAME = "HuggingFaceM4/FineVision"


def get_all_subsets_and_splits() -> list[dict]:
    """
    FineVision의 전체 subset과 각 subset의 split 목록을 동적으로 탐색해 반환한다.

    하드코딩 없이 HuggingFace API 결과 그대로 사용.
    반환 형식: [{"subset": "aokvqa", "split": "train"}, ...]
    """
    # 데이터셋에 등록된 모든 subset 이름 가져오기
    subsets = get_dataset_config_names(DATASET_NAME)

    result = []
    for subset in subsets:
        try:
            # 각 subset 내 split 목록 가져오기 (train / validation / test 등)
            splits = get_dataset_split_names(DATASET_NAME, subset)
            for split in splits:
                result.append({"subset": subset, "split": split})
        except Exception as e:
            # split 탐색 실패 시 해당 subset만 건너뛰고 계속 진행
            print(f"[explorer] {subset} split 탐색 실패: {e}")

    return result
