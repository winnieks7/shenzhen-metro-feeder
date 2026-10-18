"""Audit CPTOND Shenzhen geometry and construct a reproducible historical sample.

No source data are edited. Status is a dataset label, not an independently
verified service guarantee. Geometry matching is monotone in stop sequence.
"""
from pathlib import Path
from collections import defaultdict, Counter
import json, re, sys, hashlib
import numpy as np
import pandas as pd
import shapefile
from pyproj import Transformer
from shapely.geometry import Point, LineString

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/CPTOND2025_Shenzhen'
OUT = ROOT / 'results'
TF = Transformer.from_crs(4326, 32649, always_xy=True)


def load_layer(mode, layer):
    result = []
    with shapefile.Reader(str(DATA / mode / f'shenzhen_{mode}_{layer}.shp'), encoding='utf-8') as reader:
        for sr in reader.iterShapeRecords():
            row = sr.record.as_dict()
            xy = np.array(sr.shape.points, dtype=float)
            x, y = TF.transform(xy[:, 0], xy[:, 1])
            row['xy'] = np.column_stack((x, y))
            row['lonlat'] = xy
            row['parts'] = list(sr.shape.parts) if hasattr(sr.shape, 'parts') else []
            result.append(row)
    return result


def match_monotone(vertices, stops, tolerance=200):
    """Minimum squared-residual projection subject to nondecreasing chainage.

    Each stop has all within-tolerance segment projections as candidates.
    Dynamic programming chooses a globally monotone sequence, retaining both
    occurrences of loop termini. It never substitutes chord distances.
    """
    delta = np.diff(vertices, axis=0)
    length = np.linalg.norm(delta, axis=1)
    keep = length > 1e-8
    start, delta, length = vertices[:-1][keep], delta[keep], length[keep]
    chain = np.r_[0., np.cumsum(length)][:-1]
    prev_s = prev_cost = None
    history = []
    for stop in stops:
        t = np.clip(np.sum((stop-start)*delta, axis=1)/(length**2), 0, 1)
        projected = start + t[:, None]*delta
        d2 = np.sum((projected-stop)**2, axis=1)
        valid = d2 <= tolerance**2
        s, cost = chain[valid] + t[valid]*length[valid], d2[valid]
        if not len(s):
            return None
        order = np.argsort(s, kind='stable'); s, cost = s[order], cost[order]
        residual = cost.copy()
        if prev_s is None:
            back = np.full(len(s), -1, dtype=int)
        else:
            # Index of prefix minimum in the previous candidate layer.
            prefix = np.empty(len(prev_cost), dtype=int)
            best = 0
            for k in range(len(prev_cost)):
                if prev_cost[k] < prev_cost[best]: best = k
                prefix[k] = best
            q = np.searchsorted(prev_s, s+1e-7, side='right')-1
            back = np.where(q >= 0, prefix[np.maximum(q, 0)], -1)
            cost = cost + np.where(back >= 0, prev_cost[np.maximum(back, 0)], np.inf)
        if not np.isfinite(cost).any():
            return None
        history.append((s, residual, back))
        prev_s, prev_cost = s, cost
    k = int(np.argmin(prev_cost))
    path, residuals = [], []
    for s, residual, back in reversed(history):
        path.append(float(s[k])); residuals.append(float(np.sqrt(residual[k])))
        k = back[k]
    return np.array(path[::-1]), np.array(residuals[::-1]), float(np.min(prev_cost))


def service_label(name):
    return name.split('(')[0].replace('（', '(').strip()


def core_bus(label):
    return bool(re.match(r'^(?:[BME]\d+[A-Z]?|\d+[A-Z]?)(?:路|线|$)', label))


def main():
    OUT.mkdir(exist_ok=True)
    routes, stops = load_layer('bus', 'routes'), load_layer('bus', 'stops')
    route_map = {r['route_cn']: r for r in routes}
    assert len(route_map) == len(routes), 'Ambiguous route-name joins'
    grouped = defaultdict(list)
    for s in stops: grouped[s['route_id']].append(s)
    audit, prepared = [], []
    for rid, group in sorted(grouped.items()):
        group.sort(key=lambda r: int(r['sequence']))
        name = group[0]['route_cn']; label = service_label(name)
        rec = dict(route_id=rid, route_cn=name, label=label, n_stops=len(group), core=core_bus(label))
        r = route_map.get(name)
        if r is None:
            rec['decision'] = 'missing_route_geometry'; audit.append(rec); continue
        rec.update(status=str(r['status']), route_type=r['route_type'], loop=str(r['loop']))
        if str(r['status']) != '1' or r['route_type'] != '普通公交':
            rec['decision'] = 'status_or_type'; audit.append(rec); continue
        sequence = [int(s['sequence']) for s in group]
        if sequence != list(range(1, len(group)+1)) or any(s['route_cn'] != name for s in group):
            rec['decision'] = 'invalid_sequence'; audit.append(rec); continue
        if len(r['parts']) > 1:
            rec['decision'] = 'multipart_geometry'; audit.append(rec); continue
        xy = np.array([s['xy'][0] for s in group])
        vertices = r['xy']
        match = match_monotone(vertices, xy, 200)
        reverse = False
        if match is None:
            match = match_monotone(vertices[::-1], xy, 200); reverse = True
        if match is None:
            rec['decision'] = 'monotone_match_failed_200m'; audit.append(rec); continue
        positions, residuals, _ = match
        rec.update(max_residual_m=float(max(residuals)), median_residual_m=float(np.median(residuals)),
                   min_chainage_step_m=float(min(np.diff(positions))), reversed=reverse)
        if np.any(np.diff(positions) < 0.01):
            rec['decision'] = 'nonpositive_stop_interval'; audit.append(rec); continue
        rec['decision'] = 'geometrically_usable'
        audit.append(rec)
        prepared.append(dict(route_id=rid, name=name, label=label, core=bool(rec['core']),
                             loop=str(r['loop']) == '1', max_residual_m=float(max(residuals)),
                             xy=xy.tolist(), chainage=positions.tolist(),
                             stop_ids=[s['stop_id'] for s in group],
                             stop_names=[s['name_cn'] for s in group],
                             vertices=(vertices[::-1] if reverse else vertices).tolist()))
    pd.DataFrame(audit).to_csv(OUT/'bus_route_audit.csv', index=False)
    mr, ms = load_layer('metro', 'routes'), load_layer('metro', 'stops')
    # June 2025 termini independently checked against official opening notices.
    allowed = {'地铁1号线','地铁2号线','地铁3号线','地铁4号线','地铁5号线','地铁6号线',
               '地铁6号线支线','地铁7号线','地铁9号线','地铁10号线','地铁11号线','地铁12号线',
               '地铁13号线','地铁14号线','地铁16号线','地铁20号线'}
    metro_audit, selected_names = [], set()
    for r in mr:
        base = service_label(r['route_cn'])
        keep = str(r['status']) == '1' and base in allowed and '晨曦' not in r['route_cn']
        metro_audit.append(dict(route_cn=r['route_cn'], status=str(r['status']), include=keep,
                                reason='June_2025_metro_scope' if keep else 'future_nonmetro_or_express_variant'))
        if keep: selected_names.add(r['route_cn'])
    pd.DataFrame(metro_audit).to_csv(OUT/'metro_route_audit.csv', index=False)
    station_groups = defaultdict(list)
    for s in ms:
        if s['route_cn'] in selected_names: station_groups[s['name_cn']].append(s)
    stations, station_audit = [], []
    for name, group in sorted(station_groups.items()):
        points = np.unique(np.array([r['xy'][0] for r in group]), axis=0)
        span = float(np.max(np.linalg.norm(points[:,None]-points[None,:], axis=2)))
        # Large interchange complexes have line-specific representative points.
        # Keep this exception explicit and test any-platform proximity later.
        wide_interchanges = {'岗厦北', '后海', '车公庙', '福民'}
        if span > 300 and (name not in wide_interchanges or span > 500):
            raise ValueError(f'Ambiguous physical station {name}: {span:.1f}m')
        xy = points.mean(axis=0)
        lines = sorted(set(service_label(s['route_cn']) for s in group))
        sid = 'S'+str(len(stations)+1).zfill(3)
        # Retain source platform coordinates; baseline representative is centroid.
        stations.append(dict(station_id=sid, name=name, xy=xy.tolist(), points=points.tolist(),
                             lines=lines, stop_ids=sorted(set(s['stop_id'] for s in group))))
        station_audit.append(dict(station_id=sid, name=name, source_rows=len(group),
                                  unique_points=len(points), span_m=span, lines=';'.join(lines)))
    pd.DataFrame(station_audit).to_csv(OUT/'metro_station_audit.csv', index=False)
    payload=dict(crs='EPSG:32649', snapshot='2025-06', routes=prepared, stations=stations)
    (OUT/'prepared_network.json').write_text(json.dumps(payload,ensure_ascii=False))
    summary=dict(raw_bus_routes=len(routes), raw_bus_stop_rows=len(stops), raw_bus_route_ids=len(grouped),
                 bus_decisions=dict(Counter(r['decision'] for r in audit)),
                 core_usable_by_tolerance={str(t):sum(r['core'] and r['max_residual_m']<=t for r in prepared) for t in [50,100,200]},
                 all_ordinary_usable_by_tolerance={str(t):sum(r['max_residual_m']<=t for r in prepared) for t in [50,100,200]},
                 metro_raw_routes=len(mr), metro_kept_directions=len(selected_names),
                 metro_unique_stations=len(stations), max_station_group_span_m=max(s['span_m'] for s in station_audit))
    (OUT/'network_audit_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)


if __name__ == '__main__': main()
