"""Enforce the project-wide PowerPoint typography contract in editable decks."""
from __future__ import annotations

import os
import re
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DECKS = [ROOT / "deliverables/04_presentation/01_FOREST_CODE_TWO_PROPERTY_WORKED_EXAMPLES_20260930.pptx"]


def update(path: Path) -> None:
    fd, name = tempfile.mkstemp(suffix=".pptx", dir=path.parent); os.close(fd); temp=Path(name)
    with zipfile.ZipFile(path) as src, zipfile.ZipFile(temp,"w",zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            data=src.read(item.filename)
            if item.filename.startswith("ppt/slides/") and item.filename.endswith(".xml"):
                text=data.decode("utf-8")
                text=re.sub(r' sz="(\d+)"',lambda m:f' sz="{min(4000,max(2000,int(m.group(1))))}"',text)
                data=text.encode("utf-8")
            elif item.filename.startswith("ppt/theme/") and item.filename.endswith(".xml"):
                text=data.decode("utf-8")
                text=re.sub(r'(<a:(?:latin|ea|cs)[^>]*typeface=")[^"]*(")',r'\1Arial\2',text)
                data=text.encode("utf-8")
            dst.writestr(item,data)
    temp.replace(path)


if __name__ == "__main__":
    for deck in DECKS:
        update(deck); print(deck)
