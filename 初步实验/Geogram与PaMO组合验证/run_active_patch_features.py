"""同九小特征四方法输入，候选使用原活动面限定及完整外部保持审计。"""
import hashlib
from pathlib import Path
import sys
from active_patch_comparisons import ActiveFeatureEngines
from run_ordered_features import build_feature_source
from run_constrained_batch import HERE


if __name__=='__main__':
    identity=hashlib.sha256('\0'.join(sys.argv[1:]).encode()).hexdigest()[:12]
    folder=HERE/'实验结果/活动面限定特征入口冻结副本'/identity;folder.mkdir(parents=True,exist_ok=False)
    source=build_feature_source()
    path=folder/'active_feature_entry.py';path.write_text(source,encoding='utf-8')
    ActiveFeatureEngines.entry_path=path
    namespace=dict(__name__='active_feature_entry',__file__=str(path))
    exec(compile(source,str(path),'exec'),namespace)
    namespace['RemoteQuality']=ActiveFeatureEngines
    namespace['main']()
