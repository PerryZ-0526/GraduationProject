"""绘制实际输入到画面的逐刀与批量记录，保留不同完成前缀及完整计划分母。"""
import argparse,hashlib,json
from datetime import datetime,timezone,timedelta
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--batch',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    before=json.loads(args.baseline.read_text(encoding='utf-8'));after=json.loads(args.batch.read_text(encoding='utf-8'))
    assert before['status']=='completed_with_recorded_rejections' and after['status']=='completed' and after['mode']=='live'
    run=after['runs'][0];old=next(item for item in before['runs'] if item['hz']==after['hz'])
    assert run['planned_events']==old['planned_events']==384 and run['arrived']==384 and run['queued_at_stop']==0
    assert run['event_counts']['published_verified']==384 and run['published_updates']==77
    audit_path=args.batch.with_name('04-实际保存数组完整精确复审.json');audit=json.loads(audit_path.read_text(encoding='utf-8'))
    assert audit['parent_chain_passed'] and sum(item['kind']=='output' and item['check']['embedded_closed'] for item in audit['arrays'])==77
    args.output.mkdir(parents=True,exist_ok=False)
    plt.rcParams['font.sans-serif']=['Microsoft YaHei','SimHei','DejaVu Sans'];plt.rcParams['axes.unicode_minus']=False
    fig,axes=plt.subplots(2,1,figsize=(11,7.5),layout='constrained')
    events=[item for row in run['rows'] for item in row['input_timing']]
    axes[0].plot([item['step']+1 for item in old['frames']],[item['input_to_pixels_ms']/1000 for item in old['frames']],
        color='#bd6846',label='逐刀：210事件发布后源拒绝',lw=1.6)
    axes[0].plot([item['step']+1 for item in events],[item['input_to_pixels_ms']/1000 for item in events],
        color='#258777',label='每5事件批更新：384事件全部发布',lw=1.1)
    axes[0].axvline(211,color='#bd6846',ls=':',lw=1);axes[0].set_xlim(1,384)
    axes[0].set_ylabel('实际输入到像素延迟（秒）');axes[0].set_xlabel('原磨削事件序号');axes[0].grid(alpha=.2);axes[0].legend(loc='upper left')
    axes[0].set_title('每秒5次输入；同一原384事件计划的两次独立运行，未拼接前缀')
    batches=np.arange(1,78)
    axes[1].plot(batches,[row['active_service_to_pixels_ms']/1000 for row in run['rows']],
        label='本批开始处理到像素',color='#8b7da4',lw=1.5)
    axes[1].plot(batches,[row['input_timing'][0]['input_to_pixels_ms']/1000 for row in run['rows']],
        label='本批最早输入到像素，含凑批等待',color='#258777',lw=1.5)
    axes[1].set_xlabel('实际网格更新序号（77次覆盖384事件）');axes[1].set_ylabel('秒');axes[1].grid(alpha=.2)
    ax=axes[1].twinx();ax.step(batches,[row['queue_depth_after_display'] for row in run['rows']],
        where='mid',color='#abb1b7',alpha=.6,label='画面交付后排队事件数');ax.set_ylabel('排队事件数');ax.set_ylim(0,5)
    handles,labels=axes[1].get_legend_handles_labels();more,more_labels=ax.get_legend_handles_labels()
    axes[1].legend(handles+more,labels+more_labels,loc='upper left',fontsize=9)
    fig.suptitle('批量完整扫掠更新：球体开发路线实际NVIDIA画面\n输入预加载；包含实际等待和首次渲染，不含客户端网络与屏幕扫描',fontsize=12)
    path=args.output/'01-五次每秒批量实际画面延迟';fig.savefig(path.with_suffix('.png'),dpi=180);fig.savefig(path.with_suffix('.pdf'));plt.close(fig)
    now=datetime.now(timezone(timedelta(hours=8))).isoformat()
    binding=dict(生成时间=now,修改时间=now,修改内容='首次生成实际队列曲线',文档概述='真实输入到像素延迟及排队深度，非同父组件时延加速比',
        索引目录=['输入记录','保存复审','图表'],inputs=[dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in (args.baseline,args.batch,audit_path)],
        worker_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (args.output/'02-图表输入与方法绑定.json').write_text(json.dumps(binding,ensure_ascii=False,indent=2),encoding='utf-8')
    print(str(args.output),flush=True)


if __name__=='__main__':main()
