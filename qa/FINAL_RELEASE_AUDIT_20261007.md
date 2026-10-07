# Final release audit — 2026-10-06

## Scope

- 155,547 unique Mato Grosso rural properties.
- SIMCAR Validated, SIMCAR Digital, and Proxy input bases.
- Statewide spatial processing with 25 × 25 km tiles.

## Passed calculation controls

- Zero failures for `cons_area_2000 <= cons_area_2008 <= area_ha_car`.
- Zero APP partition closure failures; maximum absolute error below 3 × 10^-13 ha.
- Zero post-2008 clearing cases outside the 2008 consolidated footprint.
- Zero cases in which native vegetation or compliance components exceed property area.
- Zero secondary-vegetation ceiling failures.
- 155,547 workbook rows and 11,977,119 formulas verified across ten files.
- 155,547 final records and 155,547 unique property identifiers.

## Interpretation safeguard

Twenty-eight retained properties have no mapped RADAM formation coverage. They are flagged as a source-coverage limitation and must not be interpreted as observed zero native vegetation. External OCF and official comparisons are descriptive because populations, dates, legal denominators, and overlap policies are not equivalent.

## Release decision

The mathematical and spatial consistency controls passed. The release is suitable for analytical use subject to the documented RADAM coverage caveat and the non-equivalence of external benchmarks.
