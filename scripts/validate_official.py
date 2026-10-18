"""Cross-check bus labels and selected stops against the April 2025 official list.

This is a historical document comparison, not walking-path or service-day validation.
The source HTML and parsed CSV are retained in research/official_sources.
"""
from pathlib import Path
import re,json,hashlib
import pandas as pd
from coverage_analysis import Network,OUT,ROOT

URL='https://www.sz.gov.cn/xxgk/sydwxxgk/jt/gj/ywxx/gjlx/content/post_12183737.html'

def code(s):return str(s).strip().replace('路','').replace('线','').replace('号','')
def stop(s):return re.sub(r'[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳\s]','',str(s))

def main():
    path=ROOT/'research/official_sources/shenzhen_bus_april2025.csv'
    df=pd.read_csv(path).fillna('')
    if '线路编号' not in df.columns:
        df.columns=df.iloc[0];df=df.iloc[1:];df.to_csv(path,index=False)
    official={}
    for _,r in df.iterrows():
        k=code(r['线路编号']);official.setdefault(k,set())
        for col in ['上行途经站点','下行途经站点']:
            official[k]|={stop(s) for s in re.split('[、，,；;]',str(r[col])) if s.strip()}
    net=Network()
    labels=sorted(set(r['label'] for r in net.routes))
    comparison=pd.DataFrame([dict(label=s,code=code(s),official_match=code(s) in official) for s in labels])
    comparison.to_csv(OUT/'official_bus_comparison.csv',index=False)
    selected=['罗湖','福田','岗厦北','车公庙','后海','深圳北','机场','碧头','松岗','光明','深理工',
              '牛湖','双龙','坪地六联','沙田','田心','小梅沙','深圳湾口岸','会展城','科学馆',
              '仙湖路','沙井']
    rows=[];detail=[]
    for name in selected:
        st=next(s for s in net.stations if s['name']==name)
        indices=net.tree.query_ball_point(st['xy'],500)
        seen=set()
        for index in indices:
            ri,si=net.route_indices[index];r=net.routes[int(ri)]
            label=r['label'];bus_stop=r['stop_names'][int(si)];key=(label,bus_stop)
            if key in seen:continue
            seen.add(key)
            known=code(label) in official
            matched=known and stop(bus_stop) in official[code(label)]
            detail.append(dict(station=name,label=label,bus_stop=bus_stop,
                               distance_m=float(((net.points[r['point_indices'][si]]-st['xy'])**2).sum()**.5),
                               official_route_match=known,official_stop_match=matched))
        d=[x for x in detail if x['station']==name]
        rows.append(dict(station=name,nearby_label_stop_pairs=len(d),
                         official_route_matched_pairs=sum(x['official_route_match'] for x in d),
                         official_stop_matched_pairs=sum(x['official_stop_match'] for x in d),
                         example=next((x['label']+' / '+x['bus_stop'] for x in d if x['official_stop_match']),''),
                         scope='document_name_comparison_only_not_walk_validation'))
    pd.DataFrame(rows).to_csv(OUT/'station_document_check.csv',index=False)
    pd.DataFrame(detail).to_csv(OUT/'station_document_check_details.csv',index=False)
    result=dict(source_url=URL,source_period='2025-04',source_published='2025-05-20',
                source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),official_rows=len(df),
                core_labels=len(labels),official_matched_labels=int(comparison.official_match.sum()),
                checked_stations=len(rows),stations_with_match=sum(x['official_stop_matched_pairs']>0 for x in rows),
                pair_counts={k:sum(x[k] for x in rows) for k in ['nearby_label_stop_pairs','official_route_matched_pairs','official_stop_matched_pairs']},
                limit='April registry precedes June geometry; names cannot validate pedestrian connectivity or current operation.')
    (OUT/'official_validation_summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps(result,ensure_ascii=False,indent=2));print(pd.DataFrame(rows).iloc[:,:5].to_string(index=False))

if __name__=='__main__':main()
