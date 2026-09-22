import csv
import math
from collections import Counter

P = r'outputs\codigo_florestal_mt_inputs_completos.csv'
SPECIAL = {'5100359','5100805','5103304','5105150','5106315','5107958'}

def n(v):
    try: return float(v)
    except (TypeError, ValueError): return 0.0

def close(a,b):
    return math.isclose(a,b,rel_tol=1e-9,abs_tol=1e-7)

bad = Counter()
examples = []
sources = Counter()
with open(P,encoding='utf-8',newline='') as f:
    for i,row in enumerate(csv.DictReader(f),1):
        source=row['input_file_type']
        sources[source]+=1
        raw=lambda field:n(row.get(f'{source}__raw__{field}',''))
        area=raw('area_ha_car')
        mf=raw('MODULOS_FI')
        forest_raw=raw('radam_FLORESTA_ha')
        cerrado_raw=raw('radam_CERRADO_ha')
        scale=min(area/(forest_raw+cerrado_raw),1) if forest_raw+cerrado_raw>0 else 1
        forest=forest_raw*scale
        cerrado=cerrado_raw*scale
        avail=max(area-raw('cons_area_2000'),0)
        unc_f=forest*.8
        unc_c=cerrado*.35
        unc=unc_f+unc_c
        cap=min(unc,avail)
        req_f=cap*unc_f/unc if unc else 0
        req_c=cap*unc_c/unc if unc else 0
        pre_f_unc=forest*.5
        pre_c_unc=cerrado*.2
        pre_total=pre_f_unc+pre_c_unc
        pre_cap=min(pre_total,avail)
        pre_f=pre_cap*pre_f_unc/pre_total if pre_total else 0
        pre_c=pre_cap*pre_c_unc/pre_total if pre_total else 0
        special=row['mun_geocodigo_norm'] in SPECIAL
        req_mt_f=min(forest*.5,avail) if special else req_f
        exist_f=raw('radam_forest_nveg24_ha')
        exist_c=raw('radam_cerrado_nveg24_ha')
        art68_f=exist_f>=pre_f and forest>0
        art68_c=exist_c>=pre_c and cerrado>0
        small=mf<=4
        adj_f=0 if small else max(pre_f-exist_f,0) if art68_f else max(req_mt_f-exist_f,0) if special else max(req_f-exist_f,0)
        adj_c=0 if small else max(pre_c-exist_c,0) if art68_c else max(req_c-exist_c,0)
        adj=adj_f+adj_c
        app_req=raw('app')
        app_pres=raw('app_fnl_avn24') if source=='simcar_proxy' else min(raw('avn_declared_ha'),app_req)
        app_gross=max(app_req-app_pres,0)
        if mf<=1: replant=raw('appd_lte1mf_cs08')
        elif mf<=2: replant=raw('appd_1a2mf_cs08')
        elif mf<=4: replant=raw('appd_2a4mf_cs08')
        elif mf<=10: replant=raw('appd_4a10mf_cs08')
        else: replant=raw('appd_gt10mf_cs08')
        app_consolidated=raw('app_fnl_cs08') if source=='simcar_proxy' else min(raw('cons_area_2000'),app_req)
        app_consol_restore=min(replant,app_consolidated,app_gross)
        app_cap=area*.1 if mf<=2 else area*.2 if mf<=4 else float('inf')
        app_restore=min(app_consol_restore+raw('app_fnl_auas'),app_gross,app_cap)
        deficit=adj+app_restore
        secondary=n(row['secondary_vegetation_ha'])
        exist_f_secondary=exist_f+secondary
        adj_f_secondary=0 if small else 0 if exist_f_secondary>=pre_f and forest>0 else max(req_mt_f-exist_f_secondary,0) if special else max(req_f-exist_f_secondary,0)
        adj_secondary=adj_f_secondary+adj_c
        deficit_secondary=adj_secondary+app_restore
        outputs={
            'rl_adj_deficit_ha':adj,
            'app_restore_ha':app_restore,
            'calc_deficit_total_ha':deficit,
            'calc_deficit_total_with_secondary_ha':deficit_secondary,
            'compliant_baseline':deficit<=0,
            'compliant_with_secondary':deficit_secondary<=0,
        }
        for field,actual in outputs.items():
            expected=row[field]
            ok=(str(actual).lower()==expected.lower()) if isinstance(actual,bool) else close(actual,n(expected))
            if not ok:
                bad[(source,field)]+=1
                if len(examples)<25:examples.append((i,source,field,expected,actual))
        if i%25000==0:print('checked',i,flush=True)
print('rows',i,'sources',dict(sources),'mismatches',dict(bad),'examples',examples)
if bad:raise SystemExit(1)
