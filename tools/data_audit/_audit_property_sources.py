import glob
import os
import sys
print(sys.executable, flush=True)
import pyarrow.parquet as pq

patterns = [
    'out/table/*priority*.parquet',
    'delivery_2026-09-03/02_data/car_priority*.parquet',
    'data/pre/car_*/car_atp_joined*.parquet',
]
for pattern in patterns:
    for path in glob.glob(pattern):
        pf = pq.ParquetFile(path)
        print(path, pf.metadata.num_rows, len(pf.schema_arrow.names), os.path.getsize(path))
