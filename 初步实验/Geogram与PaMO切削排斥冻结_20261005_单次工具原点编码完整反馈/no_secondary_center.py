"""保留首次工具原点编码，归一化采用FP64，实际碰撞点不再减均值。"""
import numpy as np
import pamo
def install_no_secondary_center():
    def preprocess(self,points,triangles,band,margin):
        values=np.asarray(points.cpu().numpy(),np.float64)[triangles.cpu().numpy()]
        minimum=values.min(axis=0).min(axis=0)
        maximum=float((values-minimum).max())
        normalized=((values-minimum)/maximum+float(band))/float(margin)
        # 零均值使作者后续减均值及逆变换保持实际初始点数组。
        return np.ascontiguousarray(normalized),minimum,maximum,np.zeros(3,np.float32)
    pamo.PaMO.preprocess_mesh=preprocess
