"""Deterministic polygon-union analysis of directional metro feeder coverage."""
from pathlib import Path
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor
import argparse, json, time, itertools
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from shapely.geometry import Point, GeometryCollection
from shapely import union_all

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'results'


def accessible_indices(chain, transfer_indices, budget, direction):
    """Require at least one ordered bus interval; do not wrap beyond a terminus."""
    mask = np.zeros(len(chain), dtype=bool)
    for k in transfer_indices:
        d = chain[k]-chain if direction == 'inbound' else chain-chain[k]
        order = np.arange(len(chain)) < k if direction == 'inbound' else np.arange(len(chain)) > k
        mask |= order & (d > 0) & (d <= budget+1e-7)
    return np.flatnonzero(mask)


class Network:
    def __init__(self, core=True, tolerance=100, quad_segs=16, platform=False, official_only=False):
        raw=json.loads((OUT/'prepared_network.json').read_text())
        self.routes=[r for r in raw['routes'] if (r['core'] or not core) and r['max_residual_m']<=tolerance]
        if official_only:
            names=set(pd.read_csv(OUT/'official_bus_comparison.csv').query('official_match')['label'])
            self.routes=[r for r in self.routes if r['label'] in names]
        self.stations=raw['stations']; self.quad=quad_segs; self.platform=platform
        self.point_map={}; self.points=[]
        self.stop_rows=[]; self.route_indices=[]
        for ri,r in enumerate(self.routes):
            r['chainage']=np.array(r['chainage']); ids=[]
            for si,p in enumerate(r['xy']):
                # Coordinates, not names, define coincident physical points.
                key=tuple(p)
                if key not in self.point_map:
                    self.point_map[key]=len(self.points);self.points.append(p)
                ids.append(self.point_map[key]);self.stop_rows.append(p);self.route_indices.append((ri,si))
            r['point_indices']=np.array(ids)
        self.points=np.array(self.points);self.tree=cKDTree(self.stop_rows)
        self.route_indices=np.array(self.route_indices)
        self.metro_buffers={radius:union_all([Point(s['xy']).buffer(radius,quad_segs=self.quad) for s in self.stations])
                            for radius in [300,500,800]}
        self.buffers={b:[Point(xy).buffer(b,quad_segs=self.quad) for xy in self.points] for b in [200,300,500]}

    @lru_cache(maxsize=16000)
    def polygon(self, ids, buffer):
        return union_all([self.buffers[buffer][i] for i in ids])

    def memberships(self, station, radius, budget, direction):
        anchors=station['points'] if self.platform else [station['xy']]
        neighbors=sorted(set(i for p in anchors for i in self.tree.query_ball_point(p,radius)))
        route_stops={}
        for idx in neighbors:
            ri,si=self.route_indices[idx];route_stops.setdefault(int(ri),[]).append(int(si))
        answer={}
        for ri,si in route_stops.items():
            r=self.routes[ri]
            eligible=accessible_indices(r['chainage'],si,budget,direction)
            ids=tuple(sorted(set(int(i) for i in r['point_indices'][eligible])))
            if ids:answer[ri]=ids
        return answer

    def compute(self, radius, budget, buffer, tag='core', persist=True):
        start=time.monotonic();rows=[]
        for station in self.stations:
            for direction in ['inbound','outbound']:
                members=self.memberships(station,radius,budget,direction)
                polys=[self.polygon(ids,buffer) for ids in members.values()]
                all_ids=tuple(sorted(set(i for ids in members.values() for i in ids)))
                whole=self.polygon(all_ids,buffer) if all_ids else GeometryCollection()
                A=whole.area/1e6;S=sum(p.area for p in polys)/1e6
                O=1-A/S if S>0 else np.nan
                assert -1e-8<=A<=S+1e-8
                assert np.isnan(O) or -1e-8<=O<=1+1e-8
                row=dict(station_id=station['station_id'],name=station['name'],x=station['xy'][0],y=station['xy'][1],
                         direction=direction,radius_m=radius,budget_m=budget,buffer_m=buffer,tag=tag,
                         N=len(members),L=len(set(self.routes[i]['label'] for i in members)),
                         A_km2=A,S_km2=S,O=O,served_points=len(all_ids),
                         B500_km2=whole.difference(self.metro_buffers[500]).area/1e6)
                if (radius,budget,buffer)==(500,5000,300):
                    for q in [300,800]:row[f'B{q}_km2']=whole.difference(self.metro_buffers[q]).area/1e6
                rows.append(row)
        df=pd.DataFrame(rows)
        if persist:
            path=OUT/'scenarios'/f'{tag}_r{radius}_d{budget}_b{buffer}.csv';path.parent.mkdir(exist_ok=True)
            df.to_csv(path,index=False)
        print(f'{tag} r={radius} d={budget} b={buffer}: {len(df)} rows, {time.monotonic()-start:.1f}s',flush=True)
        return df

    def export_case(self, name, direction='inbound'):
        station=next(s for s in self.stations if s['name']==name)
        members=self.memberships(station,500,5000,direction)
        polys={ri:self.polygon(ids,300) for ri,ids in members.items()}
        total=union_all(list(polys.values()));rows=[];features=[]
        for ri,p in polys.items():
            others=union_all([g for k,g in polys.items() if k!=ri])
            unique=p.difference(others)
            route=self.routes[ri]
            rows.append(dict(station=name,direction=direction,route_id=route['route_id'],route=route['name'],
                             area_km2=p.area/1e6,unique_km2=unique.area/1e6))
            features.append(dict(type='Feature',properties=rows[-1],geometry=p.__geo_interface__))
        case=OUT/'cases';case.mkdir(exist_ok=True)
        pd.DataFrame(rows).to_csv(case/f'{station["station_id"]}_{direction}_routes.csv',index=False)
        (case/f'{station["station_id"]}_{direction}.geojson').write_text(json.dumps(
            dict(type='FeatureCollection',crs={'type':'name','properties':{'name':'EPSG:32649'}},
                 station=station,features=features),ensure_ascii=False))
        return station,members,polys,total


def summary(df):
    answers=[]
    for direction,g in df.groupby('direction'):
        g=g.copy();n=len(g);k=int(np.ceil(n*.2))
        def top(col):return set(g.sort_values([col,'name'],ascending=[False,True]).head(k).station_id)
        for comparator in ['N','L','S_km2']:
            rank_gap=(g.A_km2.rank(method='average',pct=True)-g[comparator].rank(method='average',pct=True)).abs()
            na=int((rank_gap>=.2-1e-9).sum())
            left=top(comparator);right=top('A_km2')
            t1=g[comparator].nlargest(k).min();t2=g.A_km2.nlargest(k).min()
            tied1=set(g.loc[g[comparator]>=t1,'station_id']);tied2=set(g.loc[g.A_km2>=t2,'station_id'])
            answers.append(dict(direction=direction,comparator=comparator,n_stations=n,
                                spearman=float(g[comparator].corr(g.A_km2,method='spearman')),
                                mean_abs_percentile_gap=float(rank_gap.mean()),
                                gap_ge20pp_n=na,top_k=k,top_overlap=len(left&right),
                                top_jaccard=len(left&right)/len(left|right),
                                tied_top_comparator_n=len(tied1),tied_top_A_n=len(tied2),
                                tied_top_overlap=len(tied1&tied2),
                                zero_service=int((g.N==0).sum()),
                                median_A=float(g.A_km2.median()),median_O=float(g.O.median())))
    return answers


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--grid',action='store_true')
    parser.add_argument('--variants',action='store_true');args=parser.parse_args()
    net=Network();base=net.compute(500,5000,300)
    base.to_csv(OUT/'baseline.csv',index=False)
    (OUT/'baseline_summary.json').write_text(json.dumps(summary(base),ensure_ascii=False,indent=2))
    if args.grid:
        settings=[s for s in itertools.product([300,500,800],[3000,5000,8000],[200,300,500]) if s!=(500,5000,300)]
        def run(s):
            # Always rebuild: a filename alone cannot establish input/code identity.
            net.compute(*s)
        with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(run,settings))
    if args.variants:
        for name,kwargs in [('all_ordinary',{'core':False}),('platform',{'platform':True}),
                            ('fine_buffer',{'quad_segs':32}),('official_matched',{'official_only':True})]:
            Network(**kwargs).compute(500,5000,300,tag=name)
    print(json.dumps(summary(base),ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':main()
