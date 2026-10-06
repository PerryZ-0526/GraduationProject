"""隔离子进程加载显式冻结入口，连接凭据仅从忽略的环境文件读取。"""
import getpass
import os
from pathlib import Path
import runpy
import sys

snapshot, entry = sys.argv[1:3]
cfg = dict(line.split('=', 1) for line in Path('.env').read_text('utf8').splitlines() if line and not line.startswith('#'))
getpass.getpass = lambda _: cfg['CUDA_SSH_PASSWORD']
os.environ['GPU_SSH_HOST'] = 'connect.westb.seetacloud.com'
sys.path.insert(0, str(Path(snapshot).resolve()))
sys.argv = [entry] + sys.argv[3:]
runpy.run_path(entry, run_name='__main__')
