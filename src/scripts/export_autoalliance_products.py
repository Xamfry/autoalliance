import argparse
from datetime import datetime
from pathlib import Path

from src.app.logging_config import configure_logging
from src.app.db import SessionLocal, init_db
from src.autoalliance.export.excel_exporter import export_autoalliance_products_to_excel


def main() -> None:
    parser = argparse.ArgumentParser(description="Export AutoAlliance products to Excel")
    parser.add_argument(
        "--output",
        default=None,
        help="Path to output xlsx file",
    )
    parser.add_argument(
        "--only-found",
        action="store_true",
        help="Export only found products",
    )

    args = parser.parse_args()

    configure_logging("export_autoalliance_products")

    init_db()

    if args.output:
        output_path = args.output
    else:
        dt = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_path = f"data/exports/autoalliance_products_{dt}.xlsx"

    Path("data/exports").mkdir(parents=True, exist_ok=True)

    with SessionLocal() as db:
        path = export_autoalliance_products_to_excel(
            db,
            output_path=output_path,
            only_found=args.only_found,
        )

    print(f"Excel создан: {path}")


if __name__ == "__main__":
    main()
    