from __future__ import annotations

import sys
import zipfile
from pathlib import Path


REPLACEMENTS = {
    b"6 October 2026": b"7 October 2026",
    b"06 October 2026": b"07 October 2026",
    b"2026-10-07": b"2026-10-07",
    b"20261007": b"20261007",
}


def update(source: Path, destination: Path) -> None:
    with zipfile.ZipFile(source, "r") as zin, zipfile.ZipFile(
        destination, "w", zipfile.ZIP_DEFLATED
    ) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename.endswith((".xml", ".rels")):
                for old, new in REPLACEMENTS.items():
                    data = data.replace(old, new)
            zout.writestr(item, data)


if __name__ == "__main__":
    update(Path(sys.argv[1]), Path(sys.argv[2]))
