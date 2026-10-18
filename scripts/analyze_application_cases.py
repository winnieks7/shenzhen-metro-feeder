"""Destination-stop interpretations fixed in research/application_case_plan.md.

Official documents corroborate service purposes and named stops, not geometry,
pedestrian access, operations, demand, or welfare. Distances use CPTOND geometry.
"""
import itertools
import json
from pathlib import Path
import numpy as np
import pandas as pd
from shapely import union_all
from shapely.geometry import Point, GeometryCollection
from coverage_analysis import Network, ROOT, accessible_indices

CASES = [
    dict(case='hospital', station='茜坑', station_en='Qiankeng', label='B862路',
         target='市二医院龙华医院', target_en='Longhua Hospital'),
    dict(case='industrial_park', station='兴东', station_en='Xingdong', label='M518路',
         target='TCL国际E城总站', target_en='TCL International E City terminus'),
    dict(case='office', station='前海湾', station_en='Qianhaiwan', label='B830路',
         target='前海大厦', target_en='Qianhai Tower'),
]


def pairs(route, station, target, radius, direction):
    distances = np.linalg.norm(np.asarray(route['xy']) - station['xy'], axis=1)
    transfer = np.flatnonzero(distances <= radius)
    targets = [j for j, name in enumerate(route['stop_names']) if name == target]
    answer = []
    for k, j in itertools.product(transfer, targets):
        if (direction == 'inbound' and j < k) or (direction == 'outbound' and j > k):
            ride = abs(route['chainage'][k] - route['chainage'][j])
            if ride > 0:
                answer.append(dict(transfer_index=int(k), target_index=j,
                                   transfer_stop=route['stop_names'][k],
                                   target_stop=target, transfer_distance_m=float(distances[k]),
                                   ride_distance_m=float(ride)))
    return sorted(answer, key=lambda x: (x['ride_distance_m'], x['transfer_distance_m']))


def main():
    net = Network()
    rows, sensitivity, details, features = [], [], [], []
    for case in CASES:
        station = next(s for s in net.stations if s['name'] == case['station'])
        selected = [(ri, r) for ri, r in enumerate(net.routes) if r['label'] == case['label']]
        assert selected and any(case['target'] in r['stop_names'] for _, r in selected)
        for direction in ['inbound', 'outbound']:
            candidates = [(ri, r, p) for ri, r in selected
                          for p in pairs(r, station, case['target'], 500, direction)]
            # Keep all candidate directional records and ordered paths in the JSON.
            details.append(dict(case=case, direction=direction, candidates=[
                dict(route_id=r['route_id'], route_name=r['name'], **p) for ri, r, p in candidates]))
            row = dict(**case, direction=direction, station_id=station['station_id'])
            if not candidates:
                row.update(baseline_eligible=False, reason='No ordered transfer-target pair')
                rows.append(row)
                continue
            ri, route, best = min(candidates, key=lambda t: t[2]['ride_distance_m'])
            eligible = best['ride_distance_m'] <= 5000 + 1e-7
            row.update(**best, route_id=route['route_id'], route_name=route['name'],
                       baseline_eligible=eligible)
            members = net.memberships(station, 500, 5000, direction)
            polys = {i: net.polygon(ids, 300) for i, ids in members.items()}
            own = polys.get(ri, GeometryCollection())
            others = union_all([p for i, p in polys.items() if i != ri])
            unique = own.difference(others)
            disk = Point(route['xy'][best['target_index']]).buffer(300, quad_segs=16)
            row.update(direction_area_km2=own.area / 1e6, exclusive_area_km2=unique.area / 1e6,
                       target_buffer_own_coverage_fraction=disk.intersection(own).area / disk.area,
                       target_buffer_other_coverage_fraction=disk.intersection(others).area / disk.area,
                       target_point_in_other_coverage=bool(others.covers(Point(route['xy'][best['target_index']]))),
                       station_N=len(members), station_A_km2=union_all(list(polys.values())).area / 1e6)
            nearest = []
            for i, point_ids in members.items():
                rr = net.routes[i]
                for j, point_id in enumerate(rr['point_indices']):
                    if point_id in point_ids:
                        delta = np.linalg.norm(np.asarray(rr['xy'][j]) - route['xy'][best['target_index']])
                        nearest.append((float(delta), rr['route_id'], rr['stop_names'][j]))
            nearest.sort()
            row.update(nearest_eligible_stop_distance_m=nearest[0][0],
                       nearest_eligible_stop_route_id=nearest[0][1],
                       nearest_eligible_stop_name=nearest[0][2])
            # Check destination inclusion independently against ordered indices, not
            # geometric coverage by a nearby, different stop buffer.
            k = np.flatnonzero(np.linalg.norm(np.asarray(route['xy']) - station['xy'], axis=1) <= 500)
            ids = accessible_indices(route['chainage'], k, 5000, direction)
            assert eligible == (best['target_index'] in ids)
            assert unique.area <= own.area + 1e-7
            assert 0 <= row['target_buffer_other_coverage_fraction'] <= 1 + 1e-10
            rows.append(row)
            for radius, budget in itertools.product([300, 500, 800], [3000, 5000, 8000]):
                ps = [p for _, r in selected for p in pairs(r, station, case['target'], radius, direction)]
                minimum = min((p['ride_distance_m'] for p in ps), default=None)
                sensitivity.append(dict(case=case['case'], direction=direction, radius_m=radius,
                                        budget_m=budget, minimum_ride_m=minimum,
                                        eligible=minimum is not None and minimum <= budget + 1e-7))
            for kind, geom in [('all_other_directions', others), ('selected_direction', own),
                               ('exclusive_area', unique), ('target_stop_buffer', disk),
                               ('metro_station', Point(station['xy'])),
                               ('transfer_stop', Point(route['xy'][best['transfer_index']])),
                               ('target_stop', Point(route['xy'][best['target_index']]))]:
                features.append(dict(type='Feature', properties=dict(case=case['case'], direction=direction,
                                                                     kind=kind, route_id=route['route_id']),
                                     geometry=geom.__geo_interface__))
    out = ROOT / 'results/application'; out.mkdir(exist_ok=True)
    pd.DataFrame(rows).to_csv(out / 'destination_connections.csv', index=False)
    pd.DataFrame(sensitivity).to_csv(out / 'destination_sensitivity.csv', index=False)
    (out / 'ordered_paths.json').write_text(json.dumps(details, ensure_ascii=False, indent=2))
    (out / 'geometry.geojson').write_text(json.dumps(dict(type='FeatureCollection',
        crs={'type':'name','properties':{'name':'EPSG:32649'}}, features=features), ensure_ascii=False))
    print(pd.DataFrame(rows)[['case','direction','route_id','baseline_eligible','transfer_distance_m',
        'ride_distance_m','direction_area_km2','exclusive_area_km2',
        'target_buffer_other_coverage_fraction','station_N']].to_string(index=False))
    print(pd.DataFrame(sensitivity).groupby(['case','direction']).eligible.sum().to_string())


if __name__ == '__main__':
    main()
