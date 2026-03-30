from datasets import get_dataset_config_names, get_dataset_split_names, load_dataset
from PIL import Image
import io
import os

DATASET_NAME = "HuggingFaceM4/FineVision"

subsets = get_dataset_config_names(DATASET_NAME)
print(f'총 subset수 : {len(subsets)}')
# for s in subsets:
#     print(f'   - {s}')

print()

# 첫 번째 subset의 split 목록만 확인
first_subset = subsets[0]
splits = get_dataset_split_names(DATASET_NAME, first_subset)
print(f"[{first_subset}] split 목록: {splits}")