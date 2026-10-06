"""核对冻结FP32坐标在共同水平面内的有理数点三角形分类。"""
import argparse
from datetime import datetime
from fractions import Fraction
import json
import hashlib
from pathlib import Path
from zoneinfo import ZoneInfo


def inside_coplanar_xy(values):
    """仅处理共同Z平面；非共面与退化三角形不按本协议解释。"""
    points=[[Fraction(float(x)) for x in row] for row in values]
    if len(points)!=4 or any(len(row)!=3 for row in points):
        raise ValueError("输入须为一点和三个三角面顶点")
    if any(row[2]!=points[0][2] for row in points):
        raise ValueError("输入不在共同水平平面")
    def orient(a,b,c):
        return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    p,a,b,c=points
    if orient(a,b,c)==0:
        raise ValueError("三角面精确退化")
    signs=[orient(a,b,p),orient(b,c,p),orient(c,a,p)]
    return all(x>=0 for x in signs) or all(x<=0 for x in signs)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--root",type=Path,required=True)
    root=parser.parse_args().root
    path=root/"01-碰撞分类精度回归清单.json"
    digest=json.loads((root/"04-碰撞分类输入摘要.json").read_text(encoding="utf-8"))
    hashes_match=hashlib.sha256(path.read_bytes()).hexdigest()==digest["manifest_sha256"]
    manifest=json.loads(path.read_text(encoding="utf-8"))
    rows=[]
    for case in manifest["cases"]:
        inside=inside_coplanar_xy(case["positions_normalized"])
        rows.append({"id":case["id"],"observed_inside":inside,
            "passed":inside==case["expected_exact_coplanar_xy_inside"]})
    result={"time_beijing":datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        "passed":hashes_match and bool(rows) and all(row["passed"] for row in rows),"rows":rows,
        "manifest_hashes_match":hashes_match,
        "scope":"有理数共同平面查询分类；不是GPU修复执行、距离或连续碰撞证书"}
    (root/"03-碰撞分类精度回归审计.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(result["passed"],len(rows))
    raise SystemExit(0 if result["passed"] else 1)
