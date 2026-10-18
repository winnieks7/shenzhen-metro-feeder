"""Derive all reported comparisons from saved scenario tables."""
import json,itertools
from pathlib import Path
import numpy as np
import pandas as pd
from coverage_analysis import OUT,Network,summary

def main():
    base=pd.read_csv(OUT/'baseline.csv'); grid=[];full=[];variants=[]
    for path in sorted((OUT/'scenarios').glob('core_*.csv')):
        df=pd.read_csv(path)
        for d,g in df.groupby('direction'):
            b=base[base.direction==d].set_index('station_id');g=g.set_index('station_id').loc[b.index].copy()
            g['rank_gap']=g.A_km2.rank(pct=True)-g.N.rank(pct=True)
            g['S_rank_gap']=g.A_km2.rank(pct=True)-g.S_km2.rank(pct=True)
            full.append(g.reset_index())
            grid.append(dict(direction=d,radius_m=int(g.radius_m.iloc[0]),budget_m=int(g.budget_m.iloc[0]),buffer_m=int(g.buffer_m.iloc[0]),
                             rho_count_area=g.N.corr(g.A_km2,method='spearman'),
                             rho_base_A=b.A_km2.corr(g.A_km2,method='spearman'),
                             gap_ge20pp=int((g.rank_gap.abs()>=.2-1e-9).sum()),
                             S_gap_ge20pp=int((g.S_rank_gap.abs()>=.2-1e-9).sum()),
                             median_overlap=float(g.O.median()),zero_service=int((g.N==0).sum())))
    assert len(grid)==54, f'Grid incomplete: {len(grid)} / 54'
    pd.DataFrame(grid).to_csv(OUT/'sensitivity_summary.csv',index=False)
    all_grid=pd.concat(full);stability=[]
    for (direction,sid),g in all_grid.groupby(['direction','station_id']):
        stability.append(dict(direction=direction,station_id=sid,name=g.name.iloc[0],
                              positive20_n=int((g.rank_gap>=.2-1e-9).sum()),negative20_n=int((g.rank_gap<=-.2+1e-9).sum()),
                              median_rank_gap=float(g.rank_gap.median()),min_rank_gap=float(g.rank_gap.min()),max_rank_gap=float(g.rank_gap.max())))
    stability=pd.DataFrame(stability);stability.to_csv(OUT/'station_stability.csv',index=False)
    for path in sorted((OUT/'scenarios').glob('*.csv')):
        if path.name.startswith('core_'):continue
        df=pd.read_csv(path)
        for direction,g in df.groupby('direction'):
            b=base[base.direction==direction].set_index('station_id');g=g.set_index('station_id').loc[b.index]
            err=(g.A_km2-b.A_km2).abs();positive=b.A_km2>0
            variants.append(dict(variant=g.tag.iloc[0],direction=direction,
                                 rho_base_A=b.A_km2.corr(g.A_km2,method='spearman'),
                                 rho_count_area=g.N.corr(g.A_km2,method='spearman'),
                                 max_abs_area_change_km2=float(err.max()),
                                 max_relative_area_change=float((err[positive]/b.A_km2[positive]).max()),
                                 median_relative_area_change=float((err[positive]/b.A_km2[positive]).median())))
    pd.DataFrame(variants).to_csv(OUT/'variant_summary.csv',index=False)
    cases=[]
    for direction,g in base.groupby('direction'):
        # A deterministic exploratory pair: largest absolute A gap among equal N.
        candidates=[]
        for n,x in g[g.N>0].groupby('N'):
            if len(x)<2:continue
            low=x.sort_values(['A_km2','name']).iloc[0];high=x.sort_values(['A_km2','name']).iloc[-1]
            candidates.append((float(high.A_km2-low.A_km2),low,high))
        _,low,high=max(candidates,key=lambda z:z[0])
        for kind,row in [('low_same_N',low),('high_same_N',high)]:
            entry=row.to_dict();entry['selection']=kind;cases.append(entry)
    case_df=pd.DataFrame(cases);case_df.to_csv(OUT/'selected_cases.csv',index=False)
    net=Network()
    for _,row in case_df.iterrows():net.export_case(row['name'],row['direction'])
    evidence=dict(baseline=summary(base),grid_count=len(grid),variant_count=len(variants),
                  grid_ranges={},stable_extremes={},cases=cases)
    for direction,g in pd.DataFrame(grid).groupby('direction'):
        evidence['grid_ranges'][direction]={col:[float(g[col].min()),float(g[col].max())]
            for col in ['rho_count_area','rho_base_A','gap_ge20pp','S_gap_ge20pp','median_overlap']}
        s=stability[stability.direction==direction]
        evidence['stable_extremes'][direction]=dict(positive_at_least22=int((s.positive20_n>=22).sum()),
                                                   negative_at_least22=int((s.negative20_n>=22).sum()))
    (OUT/'evidence_summary.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in evidence.items() if k not in ['baseline','cases']},ensure_ascii=False,indent=2))
    print(case_df[['direction','name','N','L','A_km2','S_km2','O']].to_string(index=False))

if __name__=='__main__':main()
