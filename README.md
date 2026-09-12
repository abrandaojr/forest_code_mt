# Mato Grosso Forest Code Model

Portable workflow for property-level Forest Code compliance in Mato Grosso.

## Method

Input priority:

1. SIMCAR validated
2. SIMCAR digital
3. SIMCAR proxy

All non-property spatial layers should be tiled at 25 x 25 km before spatial joins.

## Structure

- `code`: workflow, tests, helpers
- `data`: raw, preprocessed, processed data
- `doc`: method reference
- `out/table`: data products
- `out/fig`: figures
- `out/report`: manuscript and one-pagers
- `out/qgis`: QGIS project
- `qa`: audit files

## Run

```powershell
conda run -n geo python code/_01_orchestrate.py --stage reports
conda run -n geo python code/_98_test.py
conda run -n geo python code/_99_verify.py
```

Full run:

```powershell
conda run -n geo python code/_01_orchestrate.py --stage all
```

Use Git LFS for large files.

Default compute use: 80% of logical CPUs. Override with `FCM_WORKERS`.

