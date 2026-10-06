"""绘制实际已发布帧的累计几何观察，不为未执行事件补点。"""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from summarize_report_only_feedback import summarize


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder', type=Path, required=True)
    parser.add_argument('--prepared', type=Path, required=True)
    args = parser.parse_args()
    summary, curve = summarize(args.folder, args.prepared)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    routes = list(dict.fromkeys(item['route'] for item in summary['branches']))
    figure, axes = plt.subplots(len(routes), 2, figsize=(11, 3.6 * len(routes)), squeeze=False)
    for index, route in enumerate(routes):
        for branch, color in [('full', '#21558a'), ('candidate', '#c05d13')]:
            rows = [row for row in curve if row['route'] == route and row['branch'] == branch]
            if not rows:
                continue
            x = [int(row['event'][1:]) + 1 for row in rows]
            axes[index, 0].plot(x, [row['probe_max_mm'] for row in rows], color=color, label=branch)
            axes[index, 1].plot(x, [max(row['forward_p95_mm'], row['reverse_p95_mm']) for row in rows], color=color, label=branch)
        for axis, title in zip(axes[index], ['Maximum probe distance', 'Maximum of directional P95']):
            axis.set_title(route + '\n' + title)
            axis.set_xlabel('Received cutting event number')
            axis.set_ylabel('Distance to cumulative reference (mm)')
            axis.grid(alpha=.2)
            if axis.lines:
                axis.legend()
            else:
                axis.text(.5, .5, 'No recorded outputs yet', ha='center', va='center', transform=axis.transAxes)
                axis.set_xlim(1, 384)
                axis.set_ylim(bottom=0)
    # 标题明确运行中状态；探针不是连续Hausdorff界，曲线不设置接受阈值。
    figure.suptitle('Recorded outputs only | ' + summary['execution_status'] + '\nFinite probes; reference discretization error unknown')
    figure.tight_layout(rect=(0, 0, 1, .93))
    destination = args.folder / '06-偏差观察图表'
    destination.mkdir(exist_ok=True)
    figure.savefig(destination / '01-累计偏差观察.png', dpi=180)
    figure.savefig(destination / '01-累计偏差观察.pdf')
    plt.close(figure)
    print('saved finite-probe observation plots; execution status:', summary['execution_status'])


if __name__ == '__main__':
    main()
