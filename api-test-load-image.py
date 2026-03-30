from datasets import get_dataset_config_names, get_dataset_split_names, load_dataset
from PIL import Image
import io
import os

DATASET_NAME = "HuggingFaceM4/FineVision"

# ----------------------------------------
# 1단계: subset / split 목록 탐색
# ----------------------------------------
print("=" * 50)
print("[1] subset 목록 탐색")
print("=" * 50)

subsets = get_dataset_config_names(DATASET_NAME)
print(f"총 subset 수: {len(subsets)}")
for s in subsets:
    print(f"  - {s}")

print()

# 첫 번째 subset의 split 목록만 확인
first_subset = subsets[0]
splits = get_dataset_split_names(DATASET_NAME, first_subset)
print(f"[{first_subset}] split 목록: {splits}")

# ----------------------------------------
# 2단계: 레코드 1개 받아서 구조 확인
# ----------------------------------------
print()
print("=" * 50)
print(f"[2] 레코드 구조 확인 (subset={first_subset}, split={splits[0]})")
print("=" * 50)

ds = load_dataset(DATASET_NAME, first_subset, split=splits[0], streaming=True)

record = next(iter(ds))

print(f"필드 목록: {list(record.keys())}")
print()
for key, value in record.items():
    if isinstance(value, Image.Image):
        print(f"  {key}: PIL.Image — size={value.size}, mode={value.mode}")
    elif isinstance(value, bytes):
        print(f"  {key}: bytes — len={len(value)}")
    else:
        print(f"  {key}: {type(value).__name__} — {repr(value)[:100]}")

# ----------------------------------------
# 3단계: 이미지 저장 확인
# ----------------------------------------
print()
print("=" * 50)
print("[3] 이미지 저장 확인")
print("=" * 50)

save_dir = f"./data/{first_subset}/{splits[0]}"
os.makedirs(save_dir, exist_ok=True)
save_path = os.path.join(save_dir, "test_sample.jpg")

image_field = record.get("images")

if not image_field:
    print(f"이미지 필드 없음")
else:
    for idx, img in enumerate(image_field):
        save_path = os.path.join(save_dir, f"test_sample_{idx}.jpg")
        if isinstance(img, Image.Image):
            img.save(save_path)
            print(f"저장 성공 (PIL.Image): {save_path}")
        elif isinstance(img, bytes):
            Image.open(io.BytesIO(img)).save(save_path)
            print(f"저장 성공 (bytes): {save_path}")
        else:
            print(f"알 수 없는 타입: {type(img)}")