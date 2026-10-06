"""显式启用库已有Triangle支持，在新目录恢复首次重放编译失败。"""
from pathlib import Path

here=Path(__file__).resolve().parent
text=(here/'100-捕获区域原生重放准备与执行.py').read_text('utf8')
text=text.replace("folder=here/'捕获区域有界细化原生重放'","folder=here/'捕获区域有界细化原生重放修订'")
text=text.replace("root+'/region_replay'","root+'/region_replay_02'")
# 执行器需使用与实际库相同的Triangle支持宏，才能读取其公开声明。
text=text.replace("['g++','-O3','-std=c++17',","['g++','-O3','-std=c++17','-DGEOGRAM_WITH_TRIANGLE',")
(here/'102-捕获区域原生重放显式配置实际执行.py').write_text(text,'utf8')
print('显式Triangle配置入口已保存，首次编译失败记录保持')
