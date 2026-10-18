"""Illustrate directional stop selection; no empirical measurements are drawn."""
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle

ROOT = Path(__file__).resolve().parents[1]
plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['DejaVu Sans'],'font.size':10,
                     'pdf.fonttype':42,'svg.fonttype':'none'})
fig,ax=plt.subplots(figsize=(6.2,1.9))
fig.subplots_adjust(left=.025,right=.975,bottom=.04,top=.98)
ax.set(xlim=(0,10),ylim=(0,3));ax.axis('off')
blue,orange,gray='#21618c','#b46525','#4f5660'
ax.annotate('',xy=(9.5,1.35),xytext=(.5,1.35),
            arrowprops=dict(arrowstyle='->',color=gray,lw=1.4))
for x,c in [(1,blue),(2.7,blue),(5,gray),(7.3,orange),(9,orange)]:
    ax.add_patch(Circle((x,1.35),.12,fc='white',ec=c,lw=1.5,zorder=3))
ax.plot([5,5],[1.55,2.12],color=gray,ls='--',lw=1)
ax.scatter([5],[2.28],marker='s',s=95,c=gray,zorder=4)
ax.text(5,2.66,'Metro station',ha='center',va='center')
ax.text(5.2,1.92,'≤ r',ha='left',va='center',fontsize=9)
ax.text(2,2.1,'Upstream origins',color=blue,ha='center')
ax.text(8,2.1,'Downstream destinations',color=orange,ha='center')
ax.text(1.85,.91,'Bus to metro',color=blue,ha='center')
ax.text(5,.91,'Transfer stop k',ha='center',fontsize=9)
ax.text(8.15,.91,'Metro to bus',color=orange,ha='center')
ax.annotate('',xy=(4.8,.51),xytext=(.9,.51),
            arrowprops=dict(arrowstyle='<->',color=blue,lw=1))
ax.annotate('',xy=(9.1,.51),xytext=(5.2,.51),
            arrowprops=dict(arrowstyle='<->',color=orange,lw=1))
ax.text(2.85,.14,'Along-route distance ≤ d',ha='center',fontsize=9,color=blue)
ax.text(7.15,.14,'Along-route distance ≤ d',ha='center',fontsize=9,color=orange)
for ext in ['png','pdf','svg']:
    fig.savefig(ROOT/'paper/figures'/f'fig0_direction_method.{ext}',dpi=300,facecolor='white')
plt.close(fig)
