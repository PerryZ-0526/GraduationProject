"""三源三轮四方法原同输入随机计划，仅候选使用活动面限定及外部契约。"""
import hashlib
from pathlib import Path
import sys
from active_patch_comparisons import ActiveFeatureEngines
from preserved_controller_source import replace_once
from run_constrained_batch import HERE


if __name__=='__main__':
    identity=hashlib.sha256('\0'.join(sys.argv[1:]).encode()).hexdigest()[:12]
    folder=HERE/'实验结果/活动面限定配对入口冻结副本'/identity;folder.mkdir(parents=True,exist_ok=False)
    source=replace_once((HERE/'run_ordered_pairs.py').read_text(encoding='utf-8'),
        'from run_ordered_features import FeatureEngines','from active_patch_comparisons import ActiveFeatureEngines as FeatureEngines')
    path=folder/'active_pair_entry.py';path.write_text(source,encoding='utf-8')
    ActiveFeatureEngines.entry_path=path
    exec(compile(source,str(path),'exec'),dict(__name__='__main__',__file__=str(path)))
