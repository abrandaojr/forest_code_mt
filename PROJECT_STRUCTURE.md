# Project structure

| Folder | Purpose |
|---|---|
| `code/` | Canonical processing, analysis, mapping, tables, and reporting code |
| `data/` | Raw, preprocessed, and processed model inputs |
| `out/` | Reproducible intermediate tables, figures, reports, and GIS products |
| `deliverables/` | Current files intended for use or distribution |
| `doc/` | Forest Code method references and reproducibility notes |
| `qa/` | Data, spreadsheet, figure, and presentation verification |
| `scientific_presentation/` | Source and assets used to build the presentation |
| `tools/` | One-off audit, migration, and delivery utilities |
| `archive/` | Superseded packages retained only for provenance |

## Current deliverables

- `deliverables/01_excel/`: 11 property-level workbooks with formulas.
- `deliverables/02_csv/`: complete results split into four CSV files.
- `deliverables/03_figures/`: 38 final figures.
- `deliverables/04_presentation/`: current PowerPoint presentation.
- `deliverables/05_code/`: final reproducible code package.

The separate `property_size_local/` subproject is stored one directory above this repository and is intentionally excluded from Google Drive and GitHub.

Generated previews, renderings, and diagnostics belong in `qa/`. Superseded exports belong in `archive/`. The repository root should contain no temporary working files.
