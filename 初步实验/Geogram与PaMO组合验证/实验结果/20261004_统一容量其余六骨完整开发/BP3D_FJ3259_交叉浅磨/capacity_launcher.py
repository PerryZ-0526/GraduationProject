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