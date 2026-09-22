# Property-level Excel compliance model

The [final Excel files are on Google Drive](https://drive.google.com/drive/folders/1X8M8F8rexyvhcHty5VaR9f_bFl0fu8Ax). This directory contains the code that builds and checks them. The large `.xlsx` files are kept on Drive, not in this code repository.

## Contents

- 168,676 distinct properties, split across 11 workbooks because the Drive upload connector limits individual files to 100 MB.
- One property per row, keyed by `priority_key`.
- 571 columns: 123 consolidated property fields plus every column in the three property-level joined inputs (113 validated, 134 digital, 201 proxy). Input columns have source prefixes.
- 67 formula columns per property. The formulas select the validated, digital, or proxy input according to `input_file_type` and calculate RL, APP, total deficit, and the secondary-vegetation scenario in Excel.
- A `LEIA_ME` tab in each workbook explains the source order and the representation of Python infinity as `1E+99` for the APP cap.

## Rebuild

Run from the repository root after the model's input and priority stages have produced these files:

- `data/pre/car_validated/car_atp_joined_20260818.csv`
- `data/pre/car_digital/car_atp_joined_20260818.csv`
- `data/pre/car_proxy/car_atp_joined_20260818.csv`
- `out/table/forest_code_mt_priority_consolidated_with_secondary_20260818.csv`

```powershell
conda run -n geo python code/excel_property_level/build_all.py
```

The build writes its intermediate CSV and SQLite index and the 11 final workbooks under `outputs/`. The selected source row is joined by the exact `car_join` key. Other source columns are linked by the normalized property code for traceability; where those sources contain duplicate registrations, the first matching row is used. The formulas use only the selected source.

## Verification

`verify_excels.py` checks workbook integrity, 168,676 rows, 571 columns, 67 formulas per property, and the upload size limit. `compare_python.py` calls the canonical functions in `code/` and compares core RL/APP outputs for all properties. Excel recalculation was also checked on 400 rows across all three sources: 26,800 calculated cells matched the Python results. A manual edit to a raw APP input changed `app_req_ha` and `app_gross_deficit_ha` in Excel as expected.

The `.xlsx` outputs reflect the `code/` tree in this repository. The separate historical `delivery_2026-09-03/07_code/` snapshot is not the calculation reference for these workbooks.
