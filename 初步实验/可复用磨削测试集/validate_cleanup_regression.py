"""检查来源重复面负例哈希与当前清理协议；不要求未来改版仍然失败。"""
import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
import sys
from zoneinfo import ZoneInfo
import trimesh

sys.path.insert(0,str(Path(__file__).resolve().parent.parent/"Geogram与PaMO组合验证"))
from locality_cleanup import clean_provenance


def audit(root):
    """原资产不修改，错误文字与观察结果逐项保存。"""
    manifest=json.loads((root/"01-来源重复面回归资产清单.json").read_text(encoding="utf-8"))
    rows=[]
    for case in manifest["cases"]:
        files=case["files"]
        hashes=all(hashlib.sha256((root/item["file"]).read_bytes()).hexdigest()==item["sha256"] for item in files)
        roles={item["role"]:root/item["file"] for item in files}
        mesh=trimesh.load(roles["source"],force="mesh",process=False)
        labels=json.loads(roles["labels"].read_text(encoding="utf-8"))["operand_bits"]
        error=None
        try:
            clean_provenance(mesh,labels,allow_shared=True)
        except ValueError as caught:
            error=str(caught)
        rows.append({"id":case["id"],"hashes_match":hashes,"observed_error":error,
            "passed":hashes and error==case["expected_current_cleanup_error"]})
    result={"time_beijing":datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        "passed":bool(rows) and all(row["passed"] for row in rows),"rows":rows,
        "scope":"仅哈希及当前来源清理负例；非完整连续算法或GPU验证"}
    (root/"03-来源重复面回归资产审计.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    return result


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--root",type=Path,required=True)
    result=audit(parser.parse_args().root)
    print(result["passed"],len(result["rows"]))
    raise SystemExit(0 if result["passed"] else 1)
