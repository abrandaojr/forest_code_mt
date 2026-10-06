import csv
from collections import Counter, defaultdict

BASE = r'out\table\forest_code_mt_priority_consolidated_with_secondary_20260818.csv'
PATHS = {
 'simcar_validado':r'data\pre\car_validated\car_atp_joined_20260818.csv',
 'simcar_digital':r'data\pre\car_digital\car_atp_joined_20260818.csv',
 'simcar_proxy':r'data\pre\car_proxy\car_atp_joined_20260818.csv',
}
targets = defaultdict(set)
with open(BASE,encoding='utf-8-sig',newline='') as f:
 for r in csv.DictReader(f):
  targets[r['input_file_type']].add(r['car_join'])
for source,path in PATHS.items():
 c=Counter(); raw_keys=set(); matched=set(); norm_keys=set()
 with open(path,encoding='utf-8-sig',newline='') as f:
  reader=csv.DictReader(f)
  for row in reader:
   key=row.get('car_join','')
   norm=(row.get('CODIGO_CAR') or row.get('CAR_FEDERA') or row.get('car_code') or '').strip().upper()
   if norm and norm in norm_keys:c['norm_dupes']+=1
   if norm:norm_keys.add(norm)
   if key in raw_keys:c['raw_dupes']+=1
   raw_keys.add(key)
   if key in targets[source]:
    c['matched_rows']+=1
    matched.add(key)
 print(source,'raw_columns',len(reader.fieldnames),'target_keys',len(targets[source]),'matched_keys',len(matched),'missing',len(targets[source]-matched),'unique_norm',len(norm_keys),'stats',dict(c),flush=True)
 print('missing_examples',list(targets[source]-matched)[:3],flush=True)
