# GeoParquet raw provenance summary - 20261006

This manifest treats converted GeoParquets as raw-converted data when they preserve source-layer content or serve as the direct geospatial inputs for final Forest Code calculations.

## Files by package stage

| stage | files |
|---|---:|
| data/pre | 12 |
| data/proc | 8 |
| data/raw | 97 |

## Files by inferred source

| inferred source | files | size MB |
|---|---:|---:|
| Geoportal/SEMA-MT CAR Digital | 24 | 6,367.6 |
| Geoportal/SEMA-MT SIMCAR requerido/proxy | 38 | 20,613.1 |
| Geoportal/SEMA-MT SIMCAR validado | 12 | 3,008.5 |
| IBGE BC250 reference boundaries | 2 | 92.9 |
| INPE PRODES / TerraBrasilis native vegetation derivatives | 18 | 14,098.0 |
| RADAMBrasil / SEMA vegetation typology | 11 | 4,760.3 |
| Unclassified package data | 12 | 1,120.0 |

## Important interpretation

- `data/raw` contains minimal raw and raw-converted inputs.
- The final pipeline consumes precomputed property-intersect GeoParquets for the spatially heavy steps.
- `data/pre` contains current summary outputs.
- `data/proc` contains geometry masters.
- Converted GeoParquets are the retained raw inputs for this portable package.
