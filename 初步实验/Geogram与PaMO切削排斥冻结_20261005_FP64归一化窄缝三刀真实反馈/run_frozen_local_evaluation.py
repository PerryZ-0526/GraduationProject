"""先核对预登记的方法和资产摘要，再执行全部冻结路线的真实父反馈。"""
import argparse
import json
from pathlib import Path
import runpy
import sys
from run_constrained_batch import HERE
from audit_followup_candidate import sha256


def check_freeze(prepared):
    """冻结后代码或清单改变时停止，不静默更新独立评价身份。"""
    protocol=prepared/"03-独立评价方法与输入冻结.json"
    frozen=json.loads(protocol.read_text(encoding="utf-8"))
    for name,expected in frozen["method_code_sha256"].items():
        if sha256(HERE/name) != expected:
            raise ValueError("冻结方法发生变化："+name)
    for name,key in (("01-完整范围冻结清单.json","manifest_sha256"),("02-连续资产审计.json","asset_audit_sha256")):
        if sha256(prepared/name) != frozen[key]:
            raise ValueError("冻结资产登记发生变化："+name)
    audit=json.loads((prepared/"02-连续资产审计.json").read_text(encoding="utf-8"))
    if not audit["passed"]:
        raise ValueError("资产审计未通过")
    manifest=json.loads((prepared/"01-完整范围冻结清单.json").read_text(encoding="utf-8"))
    routes=manifest["routes"]
    if len(routes)!=frozen["planned_routes"] or sum(len(r["cutting_prefix_ids"]) for r in routes)!=frozen["planned_events"] or any(r["split"]!="evaluation" for r in routes):
        raise ValueError("冻结路线与完整计划分母不一致")
    return frozen


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--port",type=int,required=True)
    args=parser.parse_args()
    frozen=check_freeze(args.prepared)
    sys.argv=[frozen["entry"],"--prepared",str(args.prepared),"--output",str(args.output),"--port",str(args.port),"--split","evaluation"]
    runpy.run_path(str(HERE/frozen["entry"]),run_name="__main__")
