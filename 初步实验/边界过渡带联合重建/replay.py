"""已验收整骨序列的交互回放；不是在线几何计算或实时性能展示。"""
from pathlib import Path
import argparse
import numpy as np
import pyvista as pv

OUT = Path(__file__).parent/'实验结果'


def create_view(z=2.5, off_screen=False):
    data = np.load(OUT/f'sequence_z{z:g}.npz')
    vertices, faces = data['original_whole_vertices'].copy(), data['whole_faces']
    snapshots, mapping = data['snapshots'], data['mapping']
    mesh = pv.PolyData(vertices, np.column_stack([np.full(len(faces), 3), faces]).ravel())
    mesh.cell_data['region'] = np.r_[np.zeros(len(faces)-len(data['faces'])), np.ones(len(data['faces']))]
    plotter = pv.Plotter(off_screen=off_screen, window_size=(1100, 850), title='Validated whole-bone replay (offline)')
    plotter.set_background('#15202b')
    plotter.add_mesh(mesh, scalars='region', cmap=['#cdbb91', '#69b6b4'], clim=[0, 1],
                     show_scalar_bar=False, show_edges=True, edge_color='#465159', line_width=.35)
    plotter.camera_position = [(4, -30, 37), (-1, 0, -2), (0, 1, 0)]
    plotter.camera.parallel_projection = True
    plotter.camera.parallel_scale = 14
    state = [0]
    slider = [None]

    def update(value):
        state[0] = int(np.clip(round(value), 0, len(snapshots)-1))
        if slider[0] is not None:
            slider[0].GetRepresentation().SetValue(state[0])
        points = vertices.copy()
        points[mapping] = snapshots[state[0]]
        mesh.points = points
        plotter.add_text(f'OFFLINE validated replay | step {state[0]}/{len(snapshots)-1}\n'
                         'Arrow keys: step | Mouse: rotate / zoom', name='status', font_size=12, color='white')
        plotter.render()

    slider[0] = plotter.add_slider_widget(update, [0, len(snapshots)-1], value=0, title='Validated step',
                                         pointa=(.25, .08), pointb=(.8, .08), color='white')
    plotter.add_key_event('Right', lambda: update(state[0]+1))
    plotter.add_key_event('Left', lambda: update(state[0]-1))
    return plotter, update, len(snapshots)-1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--screenshot', action='store_true')
    args = parser.parse_args()
    plotter, update, last = create_view(off_screen=args.screenshot)
    update(last)
    if args.screenshot:
        plotter.show(screenshot=str(OUT/'整骨磨削验收回放.png'), auto_close=True)
    else:
        plotter.show()
