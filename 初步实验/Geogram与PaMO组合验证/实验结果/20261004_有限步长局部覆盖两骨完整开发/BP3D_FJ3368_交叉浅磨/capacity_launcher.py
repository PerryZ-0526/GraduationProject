# 只在隔离进程载入已冻结邻接排序扩展，不改作者安装。
import torch,sys,hashlib,importlib.util
extension_path='/root/autodl-tmp/graduation_project/constrained_20261004_简化邻接顺序隔离构建_6b28c664b1dc/sorted/build/pamo_order_sorted.so'
assert hashlib.sha256(open(extension_path,'rb').read()).hexdigest()=='c7f2719c1db6a378687c21ad009d983a9e04914b444ead2b162230a8e457b591'
spec=importlib.util.spec_from_file_location('pamo_order_sorted',extension_path)
extension=importlib.util.module_from_spec(spec)
spec.loader.exec_module(extension)
sys.modules['pamo._C']=extension
import hashlib,inspect,json
from pamo_safe_project import Stage3Config
digest=hashlib.sha256(open(inspect.getfile(Stage3Config),'rb').read()).hexdigest()
assert digest=='df1eb24db57394c32e31f6d67a58cd7ef6c25febc11aff39c5e9503ee82d6390'
original=Stage3Config.__init__
def larger(self,*args,**kwargs):
    original(self,*args,**kwargs)
    assert self.max_blocks == 1<<25
    self.max_blocks=1<<26
    print(json.dumps({'original_config_sha256':digest,'max_blocks':self.max_blocks}),flush=True)
Stage3Config.__init__=larger
import original_run_constrained_worker as worker
worker.main()