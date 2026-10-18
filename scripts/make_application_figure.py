"""Destination stops and directional footprints; all three fixed cases shown."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from shapely.geometry import shape
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import PathPatch, Patch
from matplotlib.path import Path as MplPath
from matplotlib.lines import Line2D

ROOT=Path(__file__).resolve().parents[1]
plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['DejaVu Sans'],
                     'font.size':9,'axes.titlesize':10,
                     'axes.labelsize':9,'xtick.labelsize':9,'ytick.labelsize':9,
                     'pdf.fonttype':42,'svg.fonttype':'none'})
df=pd.read_csv(ROOT/'results/application/destination_connections.csv')
features=json.loads((ROOT/'results/application/geometry.geojson').read_text())['features']

def polygons(ax,geom,origin,color,zorder):
    if geom.is_empty:return
    if geom.geom_type=='Polygon':parts=[geom]
    elif geom.geom_type=='MultiPolygon':parts=geom.geoms
    else:return
    for poly in parts:
        vertices=[];codes=[]
        for ring in [poly.exterior,*poly.interiors]:
            xy=(np.asarray(ring.coords)-origin)/1000
            vertices.extend(xy)
            codes.extend([MplPath.MOVETO]+[MplPath.LINETO]*(len(xy)-2)+[MplPath.CLOSEPOLY])
        ax.add_patch(PathPatch(MplPath(vertices,codes),facecolor=color,edgecolor='none',zorder=zorder))

def require_matplotlib_panel_alignment(fig):
    """Local check for this three-panel, equal-size, single-row layout."""
    boxes=np.array([ax.get_position().bounds for ax in fig.axes])
    if len(boxes)!=3:
        raise ValueError('Expected exactly three fixed case panels')
    # Bottom edges, widths and heights must coincide; x positions must increase.
    if not np.all(np.ptp(boxes[:,1:],axis=0)<1e-9) or not np.all(np.diff(boxes[:,0])>0):
        raise ValueError('Destination case panels are not aligned at a common scale')
    (ROOT/'paper/qa/application_panel_alignment.json').write_text(json.dumps(
        dict(status='PASS',check='Three equal axes in one row after final draw',
             bounds=boxes.tolist()),indent=2))

fig,axes=plt.subplots(1,3,figsize=(6.2,3.1),sharex=True,sharey=True)
fig.subplots_adjust(left=.085,right=.99,bottom=.27,top=.82,wspace=.10)
for panel,(ax,case,label) in enumerate(zip(axes,['hospital','industrial_park','office'],
                                        ['Hospital stop','TCL park terminus','Qianhai Tower stop'])):
    row=df[(df['case']==case)&(df.direction=='outbound')].iloc[0]
    geoms={f['properties']['kind']:shape(f['geometry']) for f in features
           if f['properties']['case']==case and f['properties']['direction']=='outbound'}
    origin=np.array(geoms['metro_station'].coords[0])
    for kind,color,z in [('all_other_directions','#e2e5e8',1),
                         ('selected_direction','#65b4b0',2),('exclusive_area','#d88b3b',3)]:
        polygons(ax,geoms[kind],origin,color,z)
    target=(np.array(geoms['target_stop'].coords[0])-origin)/1000
    ax.scatter(0,0,marker='*',s=62,c='#252c38',zorder=5)
    ax.scatter(*target,marker='o',s=22,facecolor='white',edgecolor='#252c38',linewidth=1,zorder=6)
    ax.text(.05,.94,label,transform=ax.transAxes,va='top',fontsize=9,
            bbox=dict(facecolor='white',alpha=.9,edgecolor='none',pad=1.5))
    ax.set(xlim=(-1,4),ylim=(-2.5,2.5),aspect='equal',xticks=[0,2,4],yticks=[-2,0,2])
    ax.set_title(f"{chr(97+panel)}  {row.station_en}\n{row.label[:-1]}",loc='left',pad=5)
    ax.spines[['top','right']].set_visible(False)
axes[0].set_ylabel('North of metro station (km)')
fig.text(.54,.16,'East of metro station (km)',ha='center',fontsize=9)
fig.legend(handles=[Patch(facecolor='#e2e5e8',label='Other directions'),
                    Patch(facecolor='#65b4b0',label='Selected direction'),
                    Patch(facecolor='#d88b3b',label='Exclusive area'),
                    Line2D([],[],marker='*',linestyle='none',color='#252c38',label='Metro station'),
                    Line2D([],[],marker='o',markerfacecolor='white',linestyle='none',color='#252c38',label='Destination stop')],
           loc='lower center',bbox_to_anchor=(.5,-.005),ncol=3,frameon=False,fontsize=9,
           handlelength=1,columnspacing=1.1)
fig.canvas.draw()
require_matplotlib_panel_alignment(fig)
for ext in ['pdf','png']:
    fig.savefig(ROOT/f'paper/figures/fig5_destination_connections.{ext}',dpi=300,facecolor='white')
plt.close(fig)
print('Saved all three fixed destination cases at a common scale.')
