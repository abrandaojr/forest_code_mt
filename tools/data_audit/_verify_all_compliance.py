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
        area=n(row.get('area_ha_car'))
        mf=n(row.get('MODULOS_FI'))
        forest=n(row.get('radam_forest_ha'))
        cerrado=n(row.get('radam_cerrado_ha'))
        # The statutory cut-off inputs are harmonized upstream.  In particular,
        # validated/digital records receive the proxy 2000 value through their
        # CAR join key, so the row-aligned prefixed proxy column is not the
        # authoritative value for those sources.
        cons2000=min(n(row.get('cons_area_2000')),area)
        cons2008=min(n(row.get('cons_area_2008')),area)
        veg2000=max(area-cons2000,0)
        veg2008=max(area-cons2008,0)
        unc_f=forest*.8
        unc_c=cerrado*.35
        unc=unc_f+unc_c
        req_f=unc_f
        req_c=unc_c
        pre_f_unc=forest*.5
        pre_c_unc=cerrado*.2
        pre_total=pre_f_unc+pre_c_unc
        special=row['mun_geocodigo_norm'] in SPECIAL
        exist_f=n(row.get('rl_exist_forest_ha'))
        exist_c=n(row.get('rl_exist_cerrado_ha'))
        small=mf<=4
        req_art67=min(unc,veg2008)
        req_art68=pre_total if veg2000>=pre_total else unc
        req_base=req_art67 if small else req_art68
        adj=max(req_base-(exist_f+exist_c),0)
        app_req=n(row.get('app_req_ha'))
        app_pres=n(row.get('app_preserved_ha'))
        app_gross=max(app_req-app_pres,0)
        replant=n(row.get('app_replant_raw_ha'))
        app_consolidated=n(row.get('app_consolidated_ha'))
        app_cap=area*.1 if mf<=2 else area*.2 if mf<=4 else float('inf')
        app_consol_restore=min(replant,app_consolidated,app_gross,app_cap)
        app_restore=min(app_consol_restore+n(row.get('app_restore_auas_ha')),app_gross)
        deficit=min(adj+app_restore,area)
        secondary=n(row['secondary_vegetation_ha'])
        adj_secondary=max(req_base-(exist_f+exist_c+secondary),0)
        deficit_secondary=min(adj_secondary+app_restore,area)
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
