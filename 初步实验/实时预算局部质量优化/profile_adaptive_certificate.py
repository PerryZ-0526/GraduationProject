"""以相同准确区间、近接触和长期配对口径验证第五方法，不改旧结果。"""
from pathlib import Path
import os
import subprocess
import sys

BASE=Path(__file__).resolve().parent
ROOT=Path('D:/GraduationProject实验输出/20261007_方向区间与投影源认证对照_v4')
text=(BASE/'profile_directional_certificate.py').read_text(encoding='utf-8')
text=text.replace('BASE=Path(__file__).resolve().parent',f'BASE=Path({BASE.as_posix()!r})')
text=text.replace('20261007_方向区间与投影源认证对照_v3','20261007_方向区间与投影源认证对照_v4')
text=text.replace('四方法','五方法')
text=text.replace("['reference','directional','projected','combined']","['reference','directional','projected','combined','adaptive']")
text=text.replace('variants=4','variants=5')
actual=ROOT/'profile_adaptive_certificate_actual.py';assert not actual.exists()
actual.write_text(text,encoding='utf-8')
code=subprocess.run([sys.executable,str(actual)],env=dict(os.environ,PYTHONUTF8='1')).returncode
assert code==0,code
