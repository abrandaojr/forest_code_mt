import csv
import json
import os
import sqlite3
import zlib
from collections import Counter

BASE = r'out\table\forest_code_mt_priority_consolidated_with_secondary_20260818.csv'
DEST = r'outputs\codigo_florestal_mt_inputs_completos.csv'
DB = r'outputs\_raw_input_join.sqlite'
PATHS = {
    'simcar_validado': r'data\pre\car_validated\car_atp_joined_20260818.csv',
    'simcar_digital': r'data\pre\car_digital\car_atp_joined_20260818.csv',
    'simcar_proxy': r'data\pre\car_proxy\car_atp_joined_20260818.csv',
}

with open(BASE, encoding='utf-8-sig', newline='') as f:
    base_headers = next(csv.reader(f))
raw_headers = {}
for source, path in PATHS.items():
    with open(path, encoding='utf-8-sig', newline='') as f:
        raw_headers[source] = next(csv.reader(f))

os.makedirs('outputs', exist_ok=True)
if os.path.exists(DB):
    os.remove(DB)
con = sqlite3.connect(DB)
con.execute('PRAGMA journal_mode=OFF')
con.execute('PRAGMA synchronous=OFF')
con.execute('CREATE TABLE raw (source TEXT, codekey TEXT, car_join TEXT, payload BLOB)')
counts = Counter()
for source, path in PATHS.items():
    batch = []
    with open(path, encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = (row.get('CODIGO_CAR') or row.get('CAR_FEDERA') or row.get('car_code') or '').strip().upper()
            if code in ('0', 'NAN', '<NA>'):
                code = ''
            key = code or 'NO_CAR_CODE|' + source + '|' + (row.get('car_join') or row.get('prop_id_unique') or '')
            vals = [row[h] for h in raw_headers[source]]
            payload = zlib.compress(json.dumps(vals, ensure_ascii=False, separators=(',', ':')).encode(), 3)
            batch.append((source, key, row.get('car_join', ''), payload))
            counts[source] += 1
            if len(batch) >= 5000:
                con.executemany('INSERT INTO raw VALUES (?,?,?,?)', batch)
                con.commit()
                batch.clear()
        if batch:
            con.executemany('INSERT INTO raw VALUES (?,?,?,?)', batch)
            con.commit()
    print('indexed', source, counts[source], flush=True)
con.execute('CREATE INDEX ix_raw_code ON raw(source,codekey)')
con.execute('CREATE INDEX ix_raw_join ON raw(source,car_join)')
con.commit()

all_headers = base_headers + [f'{source}__raw__{h}' for source in PATHS for h in raw_headers[source]]
coverage = Counter()
unique = set()
with open(BASE, encoding='utf-8-sig', newline='') as src, open(DEST, 'w', encoding='utf-8', newline='') as out:
    reader = csv.DictReader(src)
    writer = csv.writer(out, lineterminator='\n')
    writer.writerow(all_headers)
    for n, row in enumerate(reader, 1):
        key = row['priority_key']
        if key in unique:
            raise ValueError(f'duplicate priority_key {key}')
        unique.add(key)
        record = [row[h] for h in base_headers]
        selected = row['input_file_type']
        for source in PATHS:
            if source == selected:
                hit = con.execute('SELECT payload FROM raw WHERE source=? AND car_join=? LIMIT 1', (source, row['car_join'])).fetchone()
            else:
                hit = con.execute('SELECT payload FROM raw WHERE source=? AND codekey=? LIMIT 1', (source, key)).fetchone()
            if hit:
                record.extend(json.loads(zlib.decompress(hit[0])))
                coverage[source] += 1
            else:
                record.extend([''] * len(raw_headers[source]))
                if source == selected:
                    raise ValueError(f'missing selected raw row {source} {key}')
        writer.writerow(record)
        if n % 25000 == 0:
            print('joined', n, flush=True)
con.close()
print('rows', n, 'unique', len(unique), 'columns', len(all_headers), 'coverage', dict(coverage), 'bytes', os.path.getsize(DEST), flush=True)
if n != 169533 or len(unique) != n:
    raise ValueError('row count or uniqueness mismatch')
