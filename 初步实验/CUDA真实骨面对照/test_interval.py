"""独立100位十进制公式检查区间包含关系，以及拒绝/回滚。"""
from decimal import Decimal, localcontext
import unittest
from unittest.mock import patch
import numpy as np
from interval_device import IntervalDevice, IntervalPatch, Rejected
from experiment import load_candidate
from real_patch import local_trajectory


def truth(point, base, tools):
    with localcontext() as ctx:
        ctx.prec=100
        x,y=map(Decimal.from_float,point)
        value=Decimal.from_float(float(base))
        for row in tools:
            ax,ay,bx,by,r,z=map(Decimal.from_float,row)
            dx,dy=bx-ax,by-ay
            length=dx*dx+dy*dy
            t=Decimal(0) if not length else min(Decimal(1),max(Decimal(0),((x-ax)*dx+(y-ay)*dy)/length))
            d2=(x-ax-t*dx)**2+(y-ay-t*dy)**2
            if d2<=r*r:
                value=min(value,z-(r*r-d2).sqrt())
        return +value


class IntervalTests(unittest.TestCase):
    def test_high_precision_enclosure(self):
        rng=np.random.default_rng(20260908)
        device=IntervalDevice()
        points=np.vstack([rng.uniform(-4,4,(96,2)),[[3,0],[np.nextafter(3.,0.),0],[np.nextafter(3.,4.),0],[0,0]]])
        tools=np.array([[0.,0.,0.,0.,3.,1.8],[0.,0.,.25,.037,3.,1.8],[.25,.037,-.25,.01,3.,1.8]])
        for history in [tools[:1],tools,tools[::-1]]:
            base=np.full(len(points),4.)
            device.evaluate(points,base,history)
            for xy,b,(lo,hi) in zip(points,base,device.last_bounds):
                expected=truth(xy,b,history)
                self.assertLessEqual(Decimal.from_float(lo),expected)
                self.assertGreaterEqual(Decimal.from_float(hi),expected)

    def test_invalid_domain(self):
        device=IntervalDevice()
        for tools in [np.array([[0.,0.,1e-12,0.,3.,1.8]]),np.array([[0.,0.,0.,0.,-3.,1.8]])]:
            with self.assertRaises(Rejected):
                device.evaluate(np.zeros((1,2)),np.zeros(1),tools)

    def test_wide_interval_rolls_back(self):
        candidate,chart=load_candidate()
        device=IntervalDevice()
        model=IntervalPatch(chart,candidate,device)
        actual=device.evaluate
        def widened(*args):
            value=actual(*args)
            device.last_bounds[:,1]+=1e-3
            return value
        before=model.vertices.copy()
        with patch.object(device,'evaluate',side_effect=widened):
            with self.assertRaises(Rejected):
                model.update(local_trajectory(1.8)[0])
        np.testing.assert_array_equal(before,model.vertices)
        self.assertFalse(model.tools)


if __name__=='__main__':
    unittest.main()
