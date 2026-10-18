"""Check the added case interpretation against saved geometry and raw definitions."""
from pathlib import Path
import hashlib, json
import numpy as np
import pandas as pd
from shapely.geometry import shape
from shapely import union_all
from coverage_analysis import Network, accessible_indices

ROOT = Path(__file__).resolve().parents[1]
out = ROOT/'results'
base = pd.read_csv(out/'baseline.csv')
net = Network()
rows, checked = [], []
for sid in ['S022', 'S177']:
    for direction in ['inbound', 'outbound']:
        path = out/'cases'/f'{sid}_{direction}.geojson'
        raw = json.loads(path.read_text())
        csv_path = path.with_name(f'{sid}_{direction}_routes.csv')
        tab = pd.read_csv(csv_path)
        polys = [shape(f['geometry']) for f in raw['features']]
        union = union_all(polys)
        single = [p.difference(union_all(polys[:i]+polys[i+1:])).area/1e6
                  for i,p in enumerate(polys)]
        assert np.allclose(single, tab.unique_km2, atol=1e-10, rtol=0)
        row = base[(base.station_id==sid)&(base.direction==direction)].iloc[0]
        assert abs(union.area/1e6-row.A_km2)<1e-10
        assert abs(sum(p.area for p in polys)/1e6-row.S_km2)<1e-10
        station = next(s for s in net.stations if s['station_id']==sid)
        members = net.memberships(station,500,5000,direction)
        assert len(members)==row.N
        points = set(i for v in members.values() for i in v)
        assert len(points)==row.served_points
        assert len(set(net.routes[i]['label'] for i in members))==row.L
        best = int(np.argmax(single))
        rows.append(dict(station_id=sid,station=row['name'],direction=direction,
                         N=int(row.N),L=int(row.L),distinct_coordinates=len(points),
                         A_km2=float(row.A_km2),S_km2=float(row.S_km2),O=float(row.O),
                         largest_unique_route=tab.iloc[best].route,
                         largest_unique_km2=single[best],
                         largest_unique_footprint_km2=float(tab.iloc[best].area_km2)))
        checked.extend([path,csv_path])

# Literal quantified definition, independently expressed without a mask union.
tests = 0
for chain in [np.array([0,1000,2000,4000,6000.]),np.array([0,200,200,400.])]:
    for transfer in [[],[0],[2],[len(chain)-1],[1,len(chain)-1]]:
        for budget in [200.,1000.,3000.,5000.]:
            for direction in ['inbound','outbound']:
                expected = [j for j in range(len(chain)) if any(
                    (j<k and 0<chain[k]-chain[j]<=budget) if direction=='inbound'
                    else (j>k and 0<chain[j]-chain[k]<=budget) for k in transfer)]
                assert list(accessible_indices(chain,transfer,budget,direction))==expected
                tests += 1

grid = []
for path in sorted((out/'scenarios').glob('core_*.csv')):
    frame=pd.read_csv(path)
    for direction,g in frame.groupby('direction'):
        # Percentiles are average ranks divided by the fixed station count.
        delta=(g.A_km2.rank(method='average')-g.N.rank(method='average'))/len(g)
        for idx,value in delta.items():
            grid.append(dict(station_id=g.loc[idx,'station_id'],direction=direction,
                             positive=int(value>=.2-1e-9),negative=int(value<=-.2+1e-9)))
    checked.append(path)
freq=pd.DataFrame(grid).groupby(['station_id','direction'])[['positive','negative']].sum()
counts={d:{'positive':int((freq.xs(d,level=1).positive>=22).sum()),
           'negative':int((freq.xs(d,level=1).negative>=22).sum())}
        for d in ['inbound','outbound']}
assert counts=={'inbound':{'positive':5,'negative':6},'outbound':{'positive':4,'negative':4}}
a,b=[r for r in rows if r['direction']=='inbound']
ratio=b['A_km2']/a['A_km2']
sum_ratio=b['S_km2']/a['S_km2']
share_ratio=(1-b['O'])/(1-a['O'])
assert abs(ratio-sum_ratio*share_ratio)<1e-12
checked.extend([out/'baseline.csv',out/'prepared_network.json'])
report=dict(cases=rows,ratio_decomposition=dict(area=ratio,summed=sum_ratio,nonoverlap=share_ratio),
            ordered_reachability_checks=tests,persistence_counts=counts,
            input_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in checked})
(out/'revision_evidence_check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps({k:v for k,v in report.items() if k!='input_sha256'},ensure_ascii=False,indent=2))
