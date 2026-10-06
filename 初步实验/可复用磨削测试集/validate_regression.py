"""核对固定阻断资产哈希和原协议的正负例特征，不宣称新增独立评价。"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
import trimesh

sys.path.insert(0,str(Path(__file__).resolve().parent.parent/"Geogram与PaMO组合验证"))
from locality_retriangulate import invalid_faces
from independent_reference_recovery import validate_replayed_reference


def audit(root):
    path=root/"01-回归阻断资产清单.json"
    manifest=json.loads(path.read_text(encoding="utf-8"))
    rows=[]
    for case in manifest["cases"]:
        files=case["files"]
        hashes=all(hashlib.sha256((root/item["file"]).read_bytes()).hexdigest()==item["sha256"] for item in files)
        roles={item["role"]:root/item["file"] for item in files}
        expected=case["expected_checks_for_current_protocol"]
        if "original_invalid_input" in roles:
            original=trimesh.load(roles["original_invalid_input"],process=False)
            repaired=trimesh.load(roles["repaired"],process=False)
            observed={"original_invalid_faces":int(invalid_faces(original.vertices,original.faces).sum()),
                "repaired_invalid_faces":int(invalid_faces(repaired.vertices,repaired.faces).sum()),
                "both_closed":bool(original.is_watertight and repaired.is_watertight)}
        else:
            reference=trimesh.load(roles["unresolved_reference"],process=False)
            result,details=validate_replayed_reference(reference)
            observed={"reference_recovery_accepted":result is not None,"expected_status":details.get("status")}
        passed=hashes and all(observed[k]==v for k,v in expected.items())
        rows.append(dict(id=case["id"],passed=passed,hashes_match=hashes,observed=observed))
    result=dict(time_beijing=datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),passed=all(r["passed"] for r in rows),
        rows=rows,scope="哈希及原协议正负例特征；非连续执行或全网格精确自交证书")
    (root/"02-回归阻断资产审计.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    return result


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,required=True)
    report=audit(parser.parse_args().root)
    print(report["passed"],[(r["id"],r["passed"]) for r in report["rows"]])
    raise SystemExit(0 if report["passed"] else 1)
