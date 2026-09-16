"""轴对称竖直扫掠的分层曲面实验；不处理任意骨面、偏心裁剪或交叉工具。"""
import numpy as np
import trimesh


def connect(inner, outer):
    """按周向事件合并两个环，生成共边条带；质量由独立验收决定。"""
    n, m = len(inner), len(outer)
    faces = []
    i = j = 0
    while i < n or j < m:
        if i < n and (j == m or (i+1)*m <= (j+1)*n):
            faces.append([inner[i % n], outer[j % m], inner[(i+1) % n]])
            i += 1
        else:
            faces.append([inner[i % n], outer[j % m], outer[(j+1) % m]])
            j += 1
    return faces


def generate(center_z, radius=2., spacing=.25, outer_radius=4., preserve_tangent_seam=True):
    """从z>=radius处竖直进刀至center_z；输出圆形开放局部面，不生成整骨。"""
    if not np.all(np.isfinite([center_z, radius, spacing, outer_radius])) or not (radius > 0 and spacing > 0 and outer_radius > radius):
        raise ValueError('尺寸必须有限且为正，外边界须大于工具半径')
    if center_z >= radius:
        raise ValueError('无接触或相切不生成凹坑；需由活动边界判据处理')
    theta_max = np.arccos(max(0., center_z)/radius)
    rings = []
    count = max(1, int(np.ceil(radius*theta_max/spacing)))
    for theta in np.linspace(0, theta_max, count+1)[1:]:
        rings.append((radius*np.sin(theta), center_z-radius*np.cos(theta), 'sphere'))
    if center_z < 0:
        count = max(1, int(np.ceil(-center_z/spacing)))
        rings.extend((radius, z, 'cylinder') for z in np.linspace(center_z, 0., count+1)[1:])
        if not preserve_tangent_seam:
            # 球底与圆柱为C1连接：按连续子午弧长布点，不强制一条非特征环产生薄条带。
            sphere_length = radius*np.pi/2
            total = sphere_length-center_z
            rings = []
            for s in np.linspace(0., total, int(np.ceil(total/spacing))+1)[1:]:
                if s <= sphere_length:
                    rings.append((radius*np.sin(s/radius), center_z-radius*np.cos(s/radius), 'sphere'))
                else:
                    rings.append((radius, center_z+s-sphere_length, 'cylinder'))
    mouth_radius = rings[-1][0]
    # 交线由两侧共享同一环索引，而不是两个独立网格在显示时重合。
    count = max(1, int(np.ceil((outer_radius-mouth_radius)/spacing)))
    rings.extend((r, 0., 'plane') for r in np.linspace(mouth_radius, outer_radius, count+1)[1:])
    vertices = [[0., 0., center_z-radius]]
    faces, labels = [], []
    previous = None
    seams = []
    previous_label = 'sphere'
    for r, z, label in rings:
        n = 6*max(1, int(round(2*np.pi*r/(6*spacing))))
        angles = np.arange(n)*2*np.pi/n
        current = list(range(len(vertices), len(vertices)+n))
        vertices.extend(np.column_stack([r*np.cos(angles), r*np.sin(angles), np.full(n, z)]).tolist())
        if previous is None:
            added = [[0, current[j], current[(j+1) % n]] for j in range(n)]
        else:
            added = connect(previous, current)
        if label != previous_label:
            seams.append(previous)
        faces.extend(added)
        mixed = not preserve_tangent_seam and previous_label == 'sphere' and label == 'cylinder'
        labels.extend(['mixed' if mixed else label]*len(added))
        previous, previous_label = current, label
    mesh = trimesh.Trimesh(vertices, faces, process=False)
    return mesh, np.array(labels), seams


def residual(points, labels, center_z, radius=2.):
    """按所属活动曲面计算距离残差；不是双向Hausdorff距离证书。"""
    p = np.asarray(points)
    sphere = np.abs(np.linalg.norm(p-np.array([0, 0, center_z]), axis=-1)-radius)
    cylinder = np.abs(np.linalg.norm(p[..., :2], axis=-1)-radius)
    return np.where(labels == 'sphere', sphere, np.where(labels == 'cylinder', cylinder, np.abs(p[..., 2])))


def exact_distance(points, center_z, radius=2., outer_radius=4.):
    """旋转对称性把到有限目标曲面的距离化为子午面三段曲线的最近距离。"""
    p = np.asarray(points)
    rho, z = np.linalg.norm(p[..., :2], axis=-1), p[..., 2]
    theta_max = np.arccos(max(0., center_z)/radius)
    theta = np.clip(np.arctan2(rho, center_z-z), 0., theta_max)
    sphere = np.hypot(rho-radius*np.sin(theta), z-center_z+radius*np.cos(theta))
    mouth = radius*np.sin(theta_max)
    plane = np.hypot(rho-np.clip(rho, mouth, outer_radius), z)
    distance = np.minimum(sphere, plane)
    if center_z < 0:
        distance = np.minimum(distance, np.hypot(rho-radius, z-np.clip(z, center_z, 0.)))
    return distance
