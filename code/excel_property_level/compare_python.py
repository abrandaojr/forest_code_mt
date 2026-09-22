import csv, math, sys
import pandas as pd
from pathlib import Path

source=sys.argv[1]
limit=None if len(sys.argv)<3 or sys.argv[2]=='all' else int(sys.argv[2])
root=Path('code').resolve()
sys.path.insert(0,str(root))
sys.path.insert(0,str(root/'preprocess'))
name={'simcar_validado':'_12_preprocess_validated','simcar_digital':'_11_preprocess_digital','simcar_proxy':'_10_preprocess_proxy'}[source]
mod=__import__(name)
fields=['MODULOS_FI','area_ha_car','radam_FLORESTA_ha','radam_CERRADO_ha','cons_area_2000','auas_post2008','app','app_fnl_auas','app_fnl_cs08','app_fnl_avn24','avn_declared_ha','arl_declared_ha','radam_forest_nveg24_ha','radam_cerrado_nveg24_ha','appd_lte1mf_cs08','appd_1a2mf_cs08','appd_2a4mf_cs08','appd_4a10mf_cs08','appd_gt10mf_cs08']
rows=[]
with open(r'outputs\codigo_florestal_mt_inputs_completos.csv',encoding='utf-8',newline='') as f:
    for row in csv.DictReader(f):
        if row['input_file_type']==source:
            rows.append(row)
            if limit is not None and len(rows)==limit:break
data=[]
for row in rows:
    d={'mun_geocodigo':row['mun_geocodigo_norm']}
    for field in fields:
        key=source+'__raw__'+field
        if key in row and row[key]!='':d[field]=float(row[key])
    data.append(d)
df=pd.DataFrame(data)
out=mod.compute_forest_code_metrics(df)
check=['radam_forest_ha','radam_cerrado_ha','rl_req_forest_ha','rl_req_cerrado_ha','rl_exist_forest_ha','rl_exist_cerrado_ha','rl_adj_deficit_ha','app_preserved_ha','app_restore_ha']
bad=[]
for i,row in enumerate(rows):
    for field in check:
        a=float(out.iloc[i][field]);e=float(row[field])
        if not math.isclose(a,e,rel_tol=1e-9,abs_tol=1e-7):bad.append((i,field,e,a))
print(source,'checked',len(rows)*len(check),'mismatch_count',len(bad),'examples',bad[:12],flush=True)
if bad:raise SystemExit(1)
