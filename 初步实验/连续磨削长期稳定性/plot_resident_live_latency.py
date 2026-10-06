"""绘制真实输入到NVIDIA像素的延迟和完整计划分母，不用虚拟队列代替测量。"""
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
    parser.add_argument('--record',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();record=json.loads(args.record.read_text(encoding='utf-8'))
    if record['status']!='completed_with_recorded_rejections':raise ValueError('实际画面批次尚未终态')
    args.output.mkdir(parents=True,exist_ok=False)
    plt.rcParams['font.sans-serif']=['Microsoft YaHei','SimHei','DejaVu Sans'];plt.rcParams['axes.unicode_minus']=False
    for run in record['runs']:
        if len(run['frames'])!=run['published'] or len(run['full_saved_audits'])!=run['published']:raise ValueError('画面或保存复审数量缺失')
        if any(not item['check']['embedded_closed'] for item in run['full_saved_audits']):raise ValueError('显示网格存在复审失败')
        rejected=int(run['first_rejection'] is not None)
        counts=[run['published'],rejected,run['queued_at_stop'],run['schedule_cancelled']]
        if sum(counts)!=run['planned_events'] or run['arrived']!=sum(counts[:3]):raise ValueError('完整计划与实际入队数量不一致')
        fig,axes=plt.subplots(1,2,figsize=(11,4.3),gridspec_kw=dict(width_ratios=[2,1]))
        steps=np.array([f['step']+1 for f in run['frames']])
        for key,label,color in [('input_to_pixels_ms','实际输入到像素','#bb673d'),('waiting_ms','队列等待','#9a8f9f'),('active_service_to_pixels_ms','本次处理到像素','#278570')]:
            axes[0].plot(steps,[f[key]/1000 for f in run['frames']],label=label,color=color,lw=1.5)
        axes[0].set_xlabel('实际发布的磨削事件');axes[0].set_ylabel('秒');axes[0].legend();axes[0].grid(alpha=.2)
        axes[0].set_title(f'每秒{run["hz"]:g}次真实输入；等待随后期成本增长')
        bottom=0
        for value,label,color in zip(counts,['发布像素','源拒绝','已入队后受阻','尚未送达取消'],['#278570','#bd5a55','#b1b8c1','#e2e5e9']):
            axes[1].bar(0,value,bottom=bottom,color=color,label=f'{label} {value}')
            if value>=20:axes[1].text(0,bottom+value/2,str(value),ha='center',va='center')
            bottom+=value
        axes[1].set_xticks([0],['原384事件计划']);axes[1].set_ylim(0,410);axes[1].set_ylabel('事件数');axes[1].legend(fontsize=9,loc='upper left',bbox_to_anchor=(1,1))
        fig.suptitle('NVIDIA离屏像素实测；输入已预加载；非法后缀不冒充完整磨削',fontsize=11)
        fig.tight_layout();prefix=args.output/f'01-{run["hz"]:g}次每秒真实画面延迟'
        fig.savefig(prefix.with_suffix('.png'),dpi=180);fig.savefig(prefix.with_suffix('.pdf'));plt.close(fig)
    (args.output/'02-作图实际画面记录绑定.json').write_text(json.dumps(dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),
        source=str(args.record),sha256=hashlib.sha256(args.record.read_bytes()).hexdigest(),scope=record['timing_scope']),ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(output=str(args.output),rates=len(record['runs'])),ensure_ascii=False))


if __name__=='__main__':main()
