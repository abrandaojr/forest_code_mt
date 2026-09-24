# Mato Grosso Forest Code Model

Portable workflow for property-level Forest Code compliance in Mato Grosso.

The property-level Excel model with raw source columns and live compliance formulas is documented in [code/excel_property_level](code/excel_property_level/README.md). The final package is stored in [FOREST_CODE_MT_FINAL](https://drive.google.com/drive/folders/161HTtqc8nUkVA_R44kMz7GJ_Fglqsq4e).

## Method

Input priority:

1. SIMCAR validated
2. SIMCAR digital
3. SIMCAR proxy

All non-property spatial layers should be tiled at 25 x 25 km before spatial joins.

## Repository structure

- `code`: processing workflow, tests, audits, mapping, reporting, and Excel export
- `scientific_presentation`: source used to build the Forest Code presentation
- `doc`: Forest Code method reference
- `config.json`: project paths and runtime configuration

Raw data, generated outputs, QA renders, and final delivery files are kept outside GitHub.

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

