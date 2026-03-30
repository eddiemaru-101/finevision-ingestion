from datasets import load_dataset

DATASET_NAME = "HuggingFaceM4/FineVision"
SUBSET = "CoSyn_400k_chart"
SPLIT = "train"

ds = load_dataset(DATASET_NAME, SUBSET, split=SPLIT, streaming=True)

print('---ds----')
print(ds)
print('----------')
record = next(iter(ds))

print(f"필드 목록: {list(record.keys())}")
print()

for key, value in record.items():
    print(f"  {key}: {type(value).__name__} — {repr(value)[:100]}")