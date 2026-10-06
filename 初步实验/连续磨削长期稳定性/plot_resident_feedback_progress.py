"""绘制已终态常驻开发版本的完整计划分母与已发布前缀时延。"""
import argparse
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--folders',nargs='+',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);args=p.parse_args();args.output.mkdir(exist_ok=False)
    rows=[];bindings=[]
    for folder in args.folders:
        ledger_path=folder/'06-常驻长序列完整记录.json';time_path=folder/'07-在线阶段统计与输入积压.json'
        ledger=json.loads(ledger_path.read_text(encoding='utf-8'));timing=json.loads(time_path.read_text(encoding='utf-8'))
        if ledger['status'] not in ('completed','completed_with_recorded_failures'):raise ValueError('运行快照不能计入终态图')
        bindings.append(dict(folder=str(folder),ledger_sha256=hashlib.sha256(ledger_path.read_bytes()).hexdigest(),
                             timing_sha256=hashlib.sha256(time_path.read_bytes()).hexdigest()))
        for row in timing['runs']:
            if row['reference']:continue
            rows.append(dict(version=folder.name.split('_')[-1],**row))
    fig,axes=plt.subplots(2,2,figsize=(11,7));versions=list(dict.fromkeys(r['version'] for r in rows))
    for index,(body,name) in enumerate((('slab','Slab'),('sphere','Sphere'))):
        selected=[r for r in rows if body in r['route']];x=np.arange(len(selected))
        published=np.array([r['statuses'].get('published_verified',0) for r in selected])
        rejected=np.array([r['statuses'].get('source_rejected',0) for r in selected])
        blocked=np.array([r['statuses'].get('blocked_by_previous_invalid_source',0) for r in selected])
        if np.any(published+rejected+blocked!=384):raise ValueError('完整计划分母不是384')
        axis=axes[0,index];axis.bar(x,published,label='Published',color='#278570')
        axis.bar(x,rejected,bottom=published,label='Rejected',color='#c35555')
        axis.bar(x,blocked,bottom=published+rejected,label='Blocked',color='#e0e3e6')
        for i,value in enumerate(published):axis.text(i,value+7,str(value),ha='center',fontsize=9)
        axis.set_xticks(x,[r['version'] for r in selected]);axis.set_ylim(0,410)
        axis.set_title(name+' / full 384-event scope');axis.set_ylabel('Events');axis.legend(fontsize=8)
        axis=axes[1,index]
        for key,label,style in (('mean_ms','Mean','o-'),('p95_ms','P95','s-'),('max_ms','Maximum','^-')):
            values=[r[key] if r[key] is not None else np.nan for r in selected]
            axis.plot(x,values,style,label=label)
        axis.set_xticks(x,[r['version'] for r in selected]);axis.set_title(name+' / actual published-prefix array timing')
        axis.set_ylabel('Milliseconds');axis.set_xlabel('Development version');axis.legend(fontsize=8);axis.grid(alpha=.2)
    fig.suptitle('Frozen development routes; each version starts from initial state\nDifferent parent chains and shared machine: no causal speed comparison',fontsize=11)
    fig.tight_layout();fig.savefig(args.output/'01-完整分母与数组更新时延.png',dpi=180)
    fig.savefig(args.output/'01-完整分母与数组更新时延.pdf');plt.close(fig)
    record=dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),versions=versions,rows=rows,
                actual_record_bindings=bindings,scope='终态完整384分母；时延只覆盖实际发布前缀，不含渲染或临床精度保证')
    (args.output/'02-作图输入绑定与范围.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(output=str(args.output),versions=versions),ensure_ascii=False))


if __name__=='__main__':main()
