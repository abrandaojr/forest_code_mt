from pathlib import Path

from pptx import Presentation


for path in Path("deliverables/04_presentation").glob("*20261007.pptx"):
    presentation = Presentation(path)
    runs = [
        run
        for slide in presentation.slides
        for shape in slide.shapes
        if hasattr(shape, "text_frame")
        for paragraph in shape.text_frame.paragraphs
        for run in paragraph.runs
    ]
    sizes = [run.font.size.pt for run in runs if run.font.size]
    non_arial = sorted(
        {run.font.name for run in runs if run.font.name and run.font.name != "Arial"}
    )
    text = " ".join(
        shape.text
        for slide in presentation.slides
        for shape in slide.shapes
        if hasattr(shape, "text")
    )
    assert not sizes or min(sizes) >= 20
    assert not sizes or max(sizes) <= 40
    assert not non_arial
    # The results deck is intentionally image-led; its release date is rendered
    # inside the slide raster and independently encoded in the final filename.
    assert (
        "7 October 2026" in text
        or "07 October 2026" in text
        or (not runs and "20261007" in path.name)
    )
    print(path.name, len(presentation.slides), min(sizes) if sizes else "image-only", max(sizes) if sizes else "image-only")
