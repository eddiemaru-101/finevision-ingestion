import io
from pathlib import Path

from PIL import Image


def save_images(record: dict, subset: str, split: str, record_id: str) -> list[str]:
    """
    레코드 내 이미지 리스트를 로컬 디렉토리에 저장하고 저장 경로 리스트를 반환한다.

    저장 경로 규칙: ./data/{subset}/{split}/{record_id}_{image_index}.jpg
    - 이미지가 없으면 빈 리스트 반환 (에러 발생 금지)
    - PIL.Image 객체면 바로 .save() 사용
    - bytes로 넘어온 경우 io.BytesIO로 변환 후 저장
    - 원본 포맷 무관하게 .jpg로 통일 (학습 라이브러리 호환성 최대화)
    """
    images = record.get("images") or []
    if not images:
        # images 필드 없거나 빈 리스트 → 빈 리스트 반환 (레코드 자체는 버리지 않음)
        return []

    # 저장 디렉토리 생성 (없으면 자동 생성)
    save_dir = Path("data/images") / subset / split
    save_dir.mkdir(parents=True, exist_ok=True)

    paths = []
    for idx, img in enumerate(images):
        file_path = save_dir / f"{record_id}_{idx}.jpg"

        if isinstance(img, bytes):
            # bytes 타입이면 PIL.Image로 열어서 저장
            img = Image.open(io.BytesIO(img))

        # PIL.Image 계열 (PngImageFile 등 하위 클래스 포함) → RGB 변환 후 JPEG 저장
        # RGBA, P 모드 등 JPEG 비호환 모드를 RGB로 통일
        img.convert("RGB").save(str(file_path), format="JPEG")
        paths.append(str(file_path))

    return paths
