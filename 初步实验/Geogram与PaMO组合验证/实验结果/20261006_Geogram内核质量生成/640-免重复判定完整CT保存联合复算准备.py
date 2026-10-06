"""复用既有只读完整父链检查，绑定本次实际源码和完整ZIP。"""
from pathlib import Path
here=Path(__file__).resolve().parent
source=(here/'603-保留好区顶点CT完整归档联合复算.py').read_text('utf8')
for old,new in [('保留好区顶点原生CT十六刀全部实际输出','免重复判定原生CT十六刀全部实际输出'),('602-保留好区顶点原生CT十六刀完整归档','637-免重复判定完整CT十六刀完整归档'),('597-保留好区顶点原生CT十六刀冻结清单','632-免重复判定完整CT十六刀输入清单'),('595-保留好区顶点免重建实际原生编译记录','625-已保留接缝顶点免重复判定原生构建记录'),('604-保留好区顶点原生CT十六刀保存联合复算','641-免重复判定原生CT十六刀保存联合复算')]:
    source=source.replace(old,new)
code=here/'免重复判定CT只读复算临时执行.py'
# 直接以内存编译执行，避免产生无序号文档或重复输出。
exec(compile(source,str(code),'exec'),{'__file__':str(code),'__name__':'__main__'})
