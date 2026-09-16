"""以相同XY窗口显示末步真实骨面三角形，不用生成图像伪造网格。"""
from pathlib import Path
import argparse
import sys
import numpy as np
import trimesh
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'局部区域重建阶段一'))
from patch_model import mesh_quality


def main(folder):
    local = np.load(folder/'2_cpu.npz')
    meshes = [trimesh.Trimesh(local['snapshots'][-1],local['faces'],process=False)]
    meshes += [trimesh.load(folder/f'geogram_s{s}_16.obj',force='mesh',process=False) for s in (2,3)]
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei','DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
    fig, axes = plt.subplots(1,3,figsize=(15,5),constrained_layout=True)
    for ax, mesh, label in zip(axes,meshes,['局部重建 CPU/CUDA一致','Geogram 双精度 工具s2','Geogram 双精度 工具s3']):
        tri = mesh.triangles
        ids = np.all(tri.max(axis=1)>=[-3.8,-3.8,-2],axis=1)&np.all(tri.min(axis=1)<=[3.8,3.8,3],axis=1)
        q,angle,area = mesh_quality(mesh.vertices,mesh.faces[ids])
        bad = (q<.4)|(angle<25)|(area<=1e-12)|~np.isfinite(q)|~np.isfinite(angle)
        colors = np.where(bad[:,None],np.array([[.95,.30,.13,1.]]),np.array([[.78,.84,.88,1.]]))
        polygons=PolyCollection(tri[ids,:,:2],facecolors=colors,edgecolors='#344454',linewidths=.25)
        ax.add_collection(polygons)
        ax.set(xlim=(-3.8,3.8),ylim=(-3.8,3.8),aspect='equal',xlabel='X / mm',ylabel='Y / mm',title=label)
    fig.suptitle('同一真实肩胛骨，第16步；顶视投影，橙色为三维质量未达门槛的三角形',fontsize=13)
    fig.savefig(folder/'末步真实网格对照.png',dpi=180)
    plt.close(fig)


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('folder',type=Path)
    main(parser.parse_args().folder)
