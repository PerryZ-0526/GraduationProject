"""依据实际头文件同时启用Triangle和内置依赖，两次真实编译失败保持。"""
from pathlib import Path

here=Path(__file__).resolve().parent
text=(here/'102-捕获区域原生重放显式配置实际执行.py').read_text('utf8')
text=text.replace("folder=here/'捕获区域有界细化原生重放修订'","folder=here/'捕获区域有界细化原生重放完整配置'")
text=text.replace("root+'/region_replay_02'","root+'/region_replay_03'")
# 原生库采用内置依赖，实际头文件要求该宏才能引用正确的triangle.h。
text=text.replace("'-DGEOGRAM_WITH_TRIANGLE',","'-DGEOGRAM_WITH_TRIANGLE','-DGEOGRAM_USE_BUILTIN_DEPS',")
(here/'104-捕获区域原生重放完整配置实际执行.py').write_text(text,'utf8')
print('根据实际头文件补齐内置依赖宏')
