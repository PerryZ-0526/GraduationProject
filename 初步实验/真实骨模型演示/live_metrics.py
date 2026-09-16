"""显示已完成计算状态的指标，不将刷新频率当作几何更新速度。"""
import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg


class LiveMetrics(FigureCanvasQTAgg):
    def __init__(self, parent=None):
        self.figure = Figure(figsize=(12, 2.5), layout='constrained')
        super().__init__(self.figure)
        self.setParent(parent)
        self.setMinimumHeight(210)
        self.refresh([])

    def refresh(self, records):
        self.figure.clear()
        axes = self.figure.subplots(1, 3)
        steps = [r['step'] for r in records]
        for ax, field, title in zip(axes, ['pipeline_ms', 'faces', 'quality_bad_pct'],
                ['Geometry pipeline (ms), excludes display', 'Triangle count', 'Bad faces (%), legacy gate']):
            values = [r.get(field, np.nan) for r in records]
            ax.plot(steps, values, '.-', color='#187c82')
            ax.set_title(title, fontsize=10)
            ax.set_xlabel('Completed state')
            ax.grid(alpha=.15)
            if field == 'pipeline_ms':
                ax.axhline(100, ls='--', color='#c65a32', lw=1)
            if not len(values) or not np.isfinite(values).any():
                ax.text(.5, .5, 'Not measured', ha='center', transform=ax.transAxes)
        self.draw_idle()
