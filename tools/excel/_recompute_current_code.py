import csv, math
from collections import Counter
SRC=r'outputs\codigo_florestal_mt_inputs_completos.csv'
DST=r'outputs\codigo_florestal_mt_inputs_completos_recalculados.csv'
SPECIAL={'5100359','5100805','5103304','5105150','5106315','5107958'}
def n(x):
    try:return float(x)
    except (TypeError,ValueError):return 0.0
def fmt(x):
    return str(x)
changes=Counter()
AUDIT_FIELDS=['controle__rl_exist_total_anterior_ha','controle__calc_deficit_total_anterior_ha','controle__compliant_baseline_anterior','controle__calc_deficit_total_with_secondary_anterior_ha','controle__compliant_with_secondary_anterior']
with open(SRC,encoding='utf-8',newline='') as src,open(DST,'w',encoding='utf-8',newline='') as dst:
    rd=csv.DictReader(src);wr=csv.DictWriter(dst,fieldnames=rd.fieldnames+AUDIT_FIELDS,lineterminator='\n');wr.writeheader()
    for i,row in enumerate(rd,1):
        for new,old in zip(AUDIT_FIELDS,['rl_exist_total_ha','calc_deficit_total_ha','compliant_baseline','calc_deficit_total_with_secondary_ha','compliant_with_secondary']):
            row[new]=row[old]
        source=row['input_file_type'];raw=lambda k:n(row.get(source+'__raw__'+k,''))
        area=raw('area_ha_car');mf=raw('MODULOS_FI');rf=raw('radam_FLORESTA_ha');rc=raw('radam_CERRADO_ha')
        scale=area/(rf+rc) if rf+rc>area and rf+rc>0 else 1.0
        forest=rf*scale;cerrado=rc*scale;rt=forest+cerrado
        cons=raw('cons_area_2000');avail=max(area-cons,0)
        uf=forest*.8;uc=cerrado*.35;ut=uf+uc;cap=min(ut,avail)
        reqf=cap*uf/ut if ut else 0;reqc=cap*uc/ut if ut else 0
        pf=forest*.5;pc=cerrado*.2;pt=pf+pc;pcap=min(pt,avail)
        pref=pcap*pf/pt if pt else 0;prec=pcap*pc/pt if pt else 0
        special=row['mun_geocodigo_norm'] in SPECIAL;mtf=min(forest*.5,avail) if special else reqf
        if source=='simcar_proxy':ef=raw('radam_forest_nveg24_ha');ec=raw('radam_cerrado_nveg24_ha')
        else:
            arl=min(raw('arl_declared_ha'),area)
            ef=arl*forest/rt if rt else 0;ec=arl*cerrado/rt if rt else 0
        gf=max(reqf-ef,0);gc=max(reqc-ec,0);sf=max(ef-reqf,0);sc=max(ec-reqc,0)
        small=mf<=4;artf=ef>=pref and forest>0;artc=ec>=prec and cerrado>0
        af=0 if small else max(pref-ef,0) if artf else max(mtf-ef,0) if special else gf
        ac=0 if small else max(prec-ec,0) if artc else gc
        adj=af+ac;post=min(raw('auas_post2008'),avail);restore=min(post,adj);comp=max(adj-restore,0)
        app=raw('app');pres=raw('app_fnl_avn24') if source=='simcar_proxy' else min(raw('avn_declared_ha'),app)
        appgross=max(app-pres,0)
        replant=(raw('appd_lte1mf_cs08') if mf<=1 else raw('appd_1a2mf_cs08') if mf<=2 else raw('appd_2a4mf_cs08') if mf<=4 else raw('appd_4a10mf_cs08') if mf<=10 else raw('appd_gt10mf_cs08'))
        appcap=area*.1 if mf<=2 else area*.2 if mf<=4 else math.inf
        auas=raw('app_fnl_auas');appcons=raw('app_fnl_cs08') if source=='simcar_proxy' else min(cons,app)
        appconsrest=min(replant,appcons,appgross);apprest=min(appconsrest+auas,appgross,appcap)
        sv=max(n(row['secondary_vegetation_ha']),0);efsv=ef+sv;gfsv=max(reqf-efsv,0);sfsv=max(efsv-reqf,0)
        artfsv=efsv>=pref and forest>0
        afsv=0 if small else 0 if artfsv else max(mtf-efsv,0) if special else gfsv
        adjsv=afsv+ac;restsv=min(adjsv,post);compsv=max(adjsv-restsv,0)
        deficit=adj+apprest;deficitsv=adjsv+apprest;compliant=deficit<=0;compliantsv=deficitsv<=0
        out={
          'MODULOS_FI':mf,'area_ha_car':area,'radam_FLORESTA_ha':rf,'radam_CERRADO_ha':rc,'radam_forest_ha':forest,'radam_cerrado_ha':cerrado,'radam_total_ha':rt,
          'rl_req_uncapped_forest_ha':uf,'rl_req_uncapped_cerrado_ha':uc,'rl_req_uncapped_total_ha':ut,'rl_req_forest_ha':reqf,'rl_req_cerrado_ha':reqc,'rl_req_total_ha':reqf+reqc,
          'rl_req_pre2000_forest_ha':pref,'rl_req_pre2000_cerrado_ha':prec,'rl_req_mt_forest_ha':mtf,
          'rl_exist_forest_ha':ef,'rl_exist_cerrado_ha':ec,'rl_exist_total_ha':ef+ec,
          'rl_gross_deficit_forest_ha':gf,'rl_gross_deficit_cerrado_ha':gc,'rl_gross_deficit_ha':gf+gc,
          'rl_surplus_forest_ha':sf,'rl_surplus_cerrado_ha':sc,'rl_surplus_total_ha':sf+sc,
          'art67_small_prop':small,'mt_special_mun':special,'art68_exempt_forest':artf,'art68_exempt_cerrado':artc,
          'rl_adj_deficit_forest_ha':af,'rl_adj_deficit_cerrado_ha':ac,'rl_adj_deficit_ha':adj,
          'rl_post2008_ha':post,'rl_restore_ha':restore,'rl_compensate_ha':comp,
          'app':app,'app_req_ha':app,'app_preserved_ha':pres,'app_gross_deficit_ha':appgross,
          'app_replant_raw_ha':replant,'app_cap_ha':appcap,'app_fnl_auas':auas,'app_fnl_cs08':raw('app_fnl_cs08'),
          'app_restore_auas_ha':auas,'app_consolidated_ha':appcons,'app_consol_restore_ha':appconsrest,'app_restore_ha':apprest,
          'cons_area_2000':cons,'auas_post2008':raw('auas_post2008'),
          'calc_gross_deficit_total_ha':gf+gc+appgross,'calc_deficit_total_ha':deficit,'secondary_vegetation_ha':sv,
          'rl_exist_forest_with_secondary_ha':efsv,'rl_gross_deficit_forest_with_secondary_ha':gfsv,
          'rl_surplus_forest_with_secondary_ha':sfsv,'rl_gross_deficit_with_secondary_ha':gfsv+gc,
          'rl_surplus_with_secondary_ha':sfsv+sc,'rl_adj_deficit_forest_with_secondary_ha':afsv,
          'rl_adj_deficit_cerrado_with_secondary_ha':ac,'rl_adj_deficit_with_secondary_ha':adjsv,
          'rl_restore_with_secondary_ha':restsv,'rl_compensate_with_secondary_ha':compsv,
          'calc_gross_deficit_total_with_secondary_ha':adjsv+appgross,
          'calc_deficit_total_with_secondary_ha':deficitsv,'secondary_deficit_reduction_ha':max(deficit-deficitsv,0),
          'compliant_baseline':compliant,'compliant_with_secondary':compliantsv,
          'secondary_changes_to_compliant':(not compliant) and compliantsv,
        }
        for k,v in out.items():
            if k not in row:raise KeyError(k)
            old=row[k];new=fmt(v)
            if old!=new:
                if isinstance(v,bool):different=old.lower()!=new.lower()
                else:different=not math.isclose(n(old),n(new),rel_tol=1e-9,abs_tol=1e-7)
                if different:changes[k]+=1
            row[k]=new
        wr.writerow(row)
        if i%25000==0:print('recomputed',i,flush=True)
print('rows',i,'changed',dict(changes),flush=True)
assert i==168676
