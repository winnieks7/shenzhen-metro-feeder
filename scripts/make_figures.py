"""Publication figures from saved results; PNG and vector PDF exports."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.colors import LinearSegmentedColormap
from shapely import contains_xy
from coverage_analysis import OUT,ROOT,Network
from prepare_network import load_layer

FIG=ROOT/'paper/figures';FIG.mkdir(parents=True,exist_ok=True)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.titlesize':11,
                     'axes.labelsize':10,'xtick.labelsize':9,'ytick.labelsize':9,
                     'pdf.fonttype':42,'savefig.dpi':300})

def save(fig,name):
    fig.savefig(FIG/f'{name}.png',bbox_inches='tight',facecolor='white')
    fig.savefig(FIG/f'{name}.pdf',bbox_inches='tight',facecolor='white')
    plt.close(fig)

def main():
    data=pd.read_csv(OUT/'baseline.csv');net=Network()
    incoming=data[data.direction=='inbound'].copy()
    incoming['gap']=(incoming.A_km2.rank(pct=True)-incoming.N.rank(pct=True))*100
    fig,ax=plt.subplots(figsize=(6.4,4.2),layout='constrained')
    selected=pd.read_csv(OUT/'metro_route_audit.csv').query('include').route_cn.tolist()
    metro=[r['xy']/1000 for r in load_layer('metro','routes') if r['route_cn'] in selected]
    ax.add_collection(LineCollection(metro,colors='#a3a9ad',linewidths=.65,zorder=1))
    sc=ax.scatter(incoming.x/1000,incoming.y/1000,c=incoming.gap,cmap='RdBu',vmin=-55,vmax=55,s=14,zorder=2)
    for cn,en in [('仙湖路','Xianhu Road'),('沙井','Shajing')]:
        r=incoming[incoming.name==cn].iloc[0]
        ax.annotate(en,(r.x/1000,r.y/1000),xytext=(7,7),textcoords='offset points',fontsize=9,
                    bbox={'facecolor':'white','edgecolor':'none','alpha':.8,'pad':1.5})
    ax.set(xlabel='UTM easting (km)',ylabel='UTM northing (km)',aspect='equal')
    cb=fig.colorbar(sc,ax=ax,shrink=.85,pad=.02);cb.set_label('Coverage rank minus count rank (percentile points)')
    save(fig,'fig1_station_rank_map')

    fig,axes=plt.subplots(1,2,figsize=(6.4,3.3),layout='constrained',sharey=True)
    for ax,(d,title) in zip(axes,[('inbound','To metro'),('outbound','From metro')]):
        g=data[data.direction==d]
        sc=ax.scatter(g.N,g.A_km2,c=g.O,cmap='viridis',vmin=0,vmax=1,s=14,alpha=.85,linewidths=0)
        zero=g[g.N==0]
        ax.scatter(zero.N,zero.A_km2,c='#666666',marker='x',s=28,linewidths=1)
        ax.set(title=title,xlabel='Eligible bus directions N',xlim=(-2,g.N.max()+3))
        ax.text(.04,.94,f'Spearman rho = {g.N.corr(g.A_km2,method="spearman"):.3f}',transform=ax.transAxes,va='top',fontsize=9)
        ax.grid(alpha=.18);ax.set_axisbelow(True)
    axes[0].set_ylabel('Non-duplicate coverage A (km²)')
    fig.colorbar(sc,ax=axes,shrink=.85,label='Spatial overlap O',pad=.02)
    save(fig,'fig2_count_coverage')

    cases=pd.read_csv(OUT/'selected_cases.csv').query('direction == "inbound"')
    fig,axes=plt.subplots(1,2,figsize=(6.4,3.8),layout='constrained',sharex=True,sharey=True)
    cmap=LinearSegmentedColormap.from_list('visible_overlap',plt.get_cmap('YlGnBu')(np.linspace(.2,1,256)))
    cmap.set_under('white')
    coord=np.linspace(-6.5,6.5,180);xx,yy=np.meshgrid(coord,coord)
    for ax,(_,row) in zip(axes,cases.iterrows()):
        station,members,polys,total=net.export_case(row['name'])
        counts=np.zeros(xx.shape)
        for poly in polys.values():counts+=contains_xy(poly,xx*1000+station['xy'][0],yy*1000+station['xy'][1])
        im=ax.pcolormesh(xx,yy,counts,cmap=cmap,vmin=1,vmax=20,shading='nearest',rasterized=True)
        ax.scatter(0,0,marker='*',s=90,c='#d93d3d',edgecolor='white',linewidth=.5)
        title='Xianhu Road' if row['name']=='仙湖路' else 'Shajing'
        ax.set(title=f"{title}\nN = {row.N}, A = {row.A_km2:.2f} km²",aspect='equal',xlabel='East of station (km)',xticks=[-5,0,5])
        ax.set_yticks([-5,0,5])
    axes[0].set_ylabel('North of station (km)')
    fig.colorbar(im,ax=axes,shrink=.82,label='Overlapping direction footprints',ticks=[1,5,10,15,20],extend='max',pad=.02)
    save(fig,'fig3_equal_count_cases')

    sensitivity=pd.read_csv(OUT/'sensitivity_summary.csv').query('direction == "inbound"')
    fig,axes=plt.subplots(2,3,figsize=(6.4,4.1),layout='constrained')
    for col,buffer in enumerate([200,300,500]):
        g=sensitivity[sensitivity.buffer_m==buffer]
        for row,(metric,fmt,cmap_) in enumerate([('rho_base_A','.2f','Blues'),('gap_ge20pp','.0f','YlOrRd')]):
            ax=axes[row,col];matrix=g.pivot(index='radius_m',columns='budget_m',values=metric).loc[[300,500,800],[3000,5000,8000]].values
            im=ax.imshow(matrix,cmap=cmap_,vmin=.75 if row==0 else 0,vmax=1 if row==0 else 100,aspect='auto')
            for i in range(3):
                for j in range(3):
                    ax.text(j,i,format(matrix[i,j],fmt),ha='center',va='center',fontsize=10,
                            color='white' if matrix[i,j]>(.9 if row==0 else 65) else 'black')
            ax.set(xticks=[0,1,2],xticklabels=['3','5','8'],yticks=[0,1,2],yticklabels=['300','500','800'])
            if row==0:ax.set_title(f'Stop buffer {buffer} m')
            else:ax.set_xlabel('Bus distance (km)')
            if col==0:ax.set_ylabel('Transfer radius (m)')
    fig.suptitle('Top: coverage rank correlation with baseline\nBottom: stations with count–coverage rank gaps ≥20 percentile points',fontsize=10)
    save(fig,'fig4_parameter_sensitivity')
    print('Saved four figures as PNG and PDF.')

if __name__=='__main__':main()
