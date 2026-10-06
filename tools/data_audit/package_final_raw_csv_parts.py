from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "outputs" / "codigo_florestal_mt_inputs_completos.csv"
DEST = ROOT / "deliverables" / "02_csv_raw"
PART_SIZE = 12_000


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    handle = None
    writer = None
    rows = 0
    part = 0
    try:
        with SOURCE.open(encoding="utf-8", newline="") as source:
            reader = csv.reader(source)
            header = next(reader)
            for row in reader:
                if rows % PART_SIZE == 0:
                    part += 1
                    if handle:
                        handle.close()
                    path = DEST / f"final_property_raw_inputs_20261006_part_{part:02d}.csv"
                    handle = path.open("w", encoding="utf-8-sig", newline="")
                    writer = csv.writer(handle, lineterminator="\n")
                    writer.writerow(header)
                writer.writerow(row)
                rows += 1
    finally:
        if handle:
            handle.close()
    print({"rows": rows, "parts": part, "columns": len(header)})


if __name__ == "__main__":
    main()
