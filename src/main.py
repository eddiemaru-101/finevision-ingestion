import argparse

from .pipeline import run


def main() -> None:
    """
    CLI 진입점.

    실행 방법:
        uv run python -m src.main --max-samples 10
        uv run python -m src.main --max-samples 100 --output-format parquet
    """
    parser = argparse.ArgumentParser(
        description="FineVision 데이터 수집 파이프라인",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=100,
        help="subset/split 조합당 최대 수집 레코드 수",
    )
    args = parser.parse_args()

    run(max_samples=args.max_samples)


if __name__ == "__main__":
    main()
