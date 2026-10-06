"""仅用已终态同源配对，绘制两种精确排除方案的组件收益与晚期耗时。"""
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
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plane',type=Path,required=True);parser.add_argument('--projected',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    records={name:json.loads(path.read_text(encoding='utf-8')) for name,path in [('plane',args.plane),('projected',args.projected)]}
    rows={}
    for name,record in records.items():
        if record['status']!='completed':raise ValueError('运行快照不能作为组件终态')
        rows[name]={}
        for item in record['pairs']:
            key=(item['body'],item['step']);rows[name].setdefault(key,[]).append(item)
    if set(rows['plane'])!=set(rows['projected']):raise ValueError('两种方案的实际输入范围不同')
    source_keys=lambda record:{(a['body'],a['step']):(a['parent_sha256'],a['source_sha256']) for a in record['assets']}
    if source_keys(records['plane'])!=source_keys(records['projected']):raise ValueError('两种方案不是同一份已保存父源数组')
    result=[]
    for key in rows['projected']:
        value=dict(body=key[0],step=key[1])
        for name in records:
            for variant in ['reference','candidate']:
                value[name+'_'+variant+'_median_ms']=float(np.median([a['comparisons'][variant]['total_elapsed_ms'] for a in rows[name][key]]))
            value[name+'_speedup']=value[name+'_reference_median_ms']/value[name+'_candidate_median_ms']
        result.append(value)
    plt.rcParams['font.sans-serif']=['Microsoft YaHei','SimHei','DejaVu Sans'];plt.rcParams['axes.unicode_minus']=False
    fig,axes=plt.subplots(1,2,figsize=(12,4.5));x=np.arange(len(result));width=.36
    for index,(name,label,color) in enumerate([('plane','三维平面排除','#ae7971'),('projected','二维投影排除','#278570')]):
        axes[0].bar(x+(index-.5)*width,[r[name+'_speedup'] for r in result],width,label=label,color=color)
    axes[0].axhline(1,color='#333333',lw=1,ls='--');axes[0].set_ylabel('同源原认证 / 候选中位耗时')
    axes[0].set_xticks(x,[('板' if r['body']=='slab' else '球')+str(r['step']) for r in result],rotation=45)
    axes[0].set_title('每项三轮交错配对；大于1表示更快');axes[0].legend()
    selected=[r for r in result if r['body']=='sphere' and r['step']>=190];x=np.arange(len(selected))
    for index,(name,label,color) in enumerate([('reference','同配置原认证','#a1aab4'),('candidate','二维投影候选','#278570')]):
        values=[r['projected_'+name+'_median_ms'] for r in selected]
        bars=axes[1].bar(x+(index-.5)*width,values,width,label=label,color=color)
        for bar,value in zip(bars,values):axes[1].text(bar.get_x()+bar.get_width()/2,value+35,f'{value:.0f}',ha='center',fontsize=9)
    axes[1].set_xticks(x,[str(r['step'])+('（非法源）' if r['step']==211 else '') for r in selected]);axes[1].set_ylabel('源认证中位耗时（毫秒）')
    axes[1].set_title('球体晚期组件；非法源仍被正确拒绝');axes[1].legend();axes[1].set_ylim(0,3600)
    fig.suptitle('同一已保存输入、相同编译选项；组件收益不能直接当作完整实时帧收益',fontsize=11)
    fig.tight_layout();fig.savefig(args.output/'01-精确排除同源组件时延.png',dpi=180)
    fig.savefig(args.output/'01-精确排除同源组件时延.pdf');plt.close(fig)
    bindings={name:dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest()) for name,path in [('plane',args.plane),('projected',args.projected)]}
    (args.output/'02-作图实际输入与同源核对.json').write_text(json.dumps(dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),
        rows=result,bindings=bindings,actual_sources_identical=True),ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(output=str(args.output),cases=len(result)),ensure_ascii=False))


if __name__=='__main__':main()
