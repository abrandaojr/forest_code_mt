import csv
from collections import Counter

P = r'outputs\codigo_florestal_mt_inputs_completos.csv'
FIELDS = ['MODULOS_FI','area_ha_car','radam_FLORESTA_ha','radam_CERRADO_ha','cons_area_2000','auas_post2008','app','app_fnl_auas','app_fnl_cs08','radam_forest_nveg24_ha','radam_cerrado_nveg24_ha','app_fnl_avn24','appd_lte1mf_cs08','appd_1a2mf_cs08','appd_2a4mf_cs08','appd_4a10mf_cs08','appd_gt10mf_cs08']
stats = Counter()
with open(P,encoding='utf-8',newline='') as f:
 reader=csv.DictReader(f)
 for row in reader:
  source=row['input_file_type']
  for field in FIELDS:
   raw=row.get(f'{source}__raw__{field}','')
   if f'{source}__raw__{field}' not in reader.fieldnames:
    stats[(source,field,'missing_column')]+=1
   elif raw=='':
    stats[(source,field,'blank')]+=1
   if field in row and raw and row[field] and raw != row[field]:
    try:
     if abs(float(raw)-float(row[field]))>1e-6:
      stats[(source,field,'different')]+=1
    except ValueError:
     if raw!=row[field]:stats[(source,field,'different')]+=1
print('columns',len(reader.fieldnames))
for k,v in sorted(stats.items()):
 if v:print(k,v)
