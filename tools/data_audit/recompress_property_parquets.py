from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq

t = Path("out/table")
for name in ("forest_code_mt_priority_consolidated_20260818", "forest_code_mt_priority_consolidated_with_secondary_20260818"):
    source, target = t / f"{name}.parquet", t / f"{name}_zstd.parquet"
    reader = pq.ParquetFile(source)
    writer = pq.ParquetWriter(target, reader.schema_arrow, compression="zstd", compression_level=9)
    try:
        for batch in reader.iter_batches(batch_size=10_000):
            writer.write_table(pa.Table.from_batches([batch]))
    finally:
        writer.close()
    print(target, target.stat().st_size)
