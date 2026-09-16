"""从指定实验目录生成消融网格和指标图，不重跑或覆盖原始结果。"""
from pathlib import Path
import argparse
import json
import pyvista as pv
import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('folder', type=Path)
    folder = parser.parse_args().folder
    data = json.loads((folder / 'results.json').read_text(encoding='utf-8'))
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), layout='constrained')
    for h in (.4, .25):
        for method in ('all_seams', 'sharp_only'):
            rows = [r for r in data['rows'] if r['method'] == method and r['spacing_mm'] == h]
            label = f'{method}, h={h}'
            axes[0].plot([r['step'] for r in rows], [r['min_angle_deg'] for r in rows], '.-', label=label)
            axes[1].plot([r['step'] for r in rows], [max(r['sampled_distances_mean_p95_p99_max_mm'][key][-1]
                for key in ('mesh_to_target', 'target_to_mesh')) for r in rows], '.-', label=label)
    axes[0].axhline(25, color='red', linestyle='--')
    axes[0].set_title('Minimum triangle angle (deg)')
    axes[1].axhline(.1, color='red', linestyle='--')
    axes[1].set_title('Sampled bidirectional maximum (mm), not certificate')
    for axis in axes:
        axis.set_xlabel('State: z=1.8,1,.25,0,-.0001,-.05,-.25,-1,-2')
        axis.legend(fontsize=8)
    fig.savefig(folder / '分层机制质量与距离.png', dpi=160)
    plt.close(fig)
    plotter = pv.Plotter(shape=(1, 2), off_screen=True, window_size=(1500, 700))
    for col, method in enumerate(('all_seams', 'sharp_only')):
        plotter.subplot(0, col)
        mesh = pv.read(folder / f'{method}_h0.4_step6.vtp')
        plotter.set_background('#102029')
        plotter.add_mesh(mesh, show_edges=True, color='#cdbb91')
        plotter.add_text(f'{method} | z=-0.05 mm\nAnalytic local patch, not real bone', font_size=12, color='white')
        plotter.camera_position = [(5, -7, 3), (0, 0, -.3), (0, 0, 1)]
    plotter.screenshot(folder / '光滑连接薄带消融.png')
    plotter.close()


if __name__ == '__main__':
    main()
