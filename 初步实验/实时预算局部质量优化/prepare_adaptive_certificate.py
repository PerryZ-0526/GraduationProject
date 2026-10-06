"""保留已完成四方法，独立生成按实际候选对数量延后准备的第五方法。"""
from pathlib import Path
import os
import shutil
import subprocess
import sys

BASE=Path(__file__).resolve().parent
ROOT=Path('D:/GraduationProject实验输出/20261007_方向区间与投影源认证对照_v4')
assert not ROOT.exists()
text=(BASE/'prepare_directional_certificate.py').read_text(encoding='utf-8')
text=text.replace('BASE=Path(__file__).resolve().parent',f'BASE=Path({BASE.as_posix()!r})')
text=text.replace('20261007_方向区间与投影源认证对照_v3','20261007_方向区间与投影源认证对照_v4')
text=text.replace('四方法独立编译与资产恢复','五方法独立编译与资产恢复')
text=text.replace("['reference','directional','projected','combined']","['reference','directional','projected','combined','adaptive']")
text=text.replace("shutil.copyfile(BASE/'directional_bounds.h',folder/'directional_bounds.h')",
    "shutil.copyfile(BASE/'directional_bounds.h',folder/'directional_bounds.h')\n        shutil.copyfile(BASE/'projected_separation.h',folder/'projected_separation.h')")
begin=text.index("        preparation=''\n")
end=text.index('        modified=once(modified,anchor,preparation+anchor)',begin)
text=text[:begin]+'''        preparation=''
        filtering=''
        if name in ['combined','adaptive']:
            modified=once(modified,'#include "directional_bounds.h"','#include "directional_bounds.h"\\n#include "projected_separation.h"')
        if name=='adaptive':
            preparation='        std::unique_ptr<DirectionalBounds> direction_bounds;std::unique_ptr<ProjectedSeparation> projection;\\n'
            # 前32767对仍直接执行原精确谓词；触发后建立数据的成本包含在认证中。
            filtering='\\n            if(checked==32768) {direction_bounds=std::make_unique<DirectionalBounds>(v,nv,f,nf);projection=std::make_unique<ProjectedSeparation>(v,f,nf);}'
            filtering+='\\n            if(direction_bounds && direction_bounds->separated(i,j)) {++direction_exclusions;return;}'
            filtering+='\\n            if(projection && projection->separated(i,j)) {++projection_exclusions;return;}'
        else:
            if name in ['directional','combined']:
                preparation+='        DirectionalBounds direction_bounds(v,nv,f,nf);\\n'
                filtering+='\\n            if(direction_bounds.separated(i,j)) {++direction_exclusions;return;}'
            if name=='projected':
                preparation+=projected
                filtering+='\\n            if(strictly_separated(a->info(),b->info())) {++projection_exclusions;return;}'
            elif name=='combined':
                preparation+='        ProjectedSeparation projection(v,f,nf);\\n'
                filtering+='\\n            if(projection.separated(i,j)) {++projection_exclusions;return;}'
'''+text[end:]
text=text.replace('variants=4','variants=5')
actual=ROOT.parent/'20261007_自适应认证实际准备.py';assert not actual.exists()
actual.write_text(text,encoding='utf-8')
code=subprocess.run([sys.executable,str(actual)],env=dict(os.environ,PYTHONUTF8='1')).returncode
shutil.copyfile(actual,ROOT/'prepare_adaptive_certificate_actual.py')
assert code==0,code
