"""从首刀静态复审生成预算对照入口，保持相同排斥算法与原始负例。"""

import hashlib
import json
from pathlib import Path


def main():
    here = Path(__file__).resolve().parent
    text = (here / "audit_thin_minimum_resolution_raw.py").read_text("utf8")
    text = text.replace('import getpass\n', 'import getpass\nimport argparse\n', 1)
    text = text.replace('    project = Path.cwd()', '    parser = argparse.ArgumentParser(description=__doc__)\n    parser.add_argument("--ratio", type=int, choices=(1, 2, 4), required=True)\n    args = parser.parse_args()\n    project = Path.cwd()', 1)
    text = text.replace("'20261005_薄壁最低分辨率256完整GPU'", "f'20261005_薄壁首刀同源简化预算对照_ratio{args.ratio}'")
    text = text.replace("'01-固定第二刀完整三阶段终态.json'", "'01-薄壁首刀完整三阶段观测终态.json'")
    text = text.replace("'20261005_薄壁首刀最低分辨率256整面维护复审'", "f'20261005_薄壁首刀预算{args.ratio}整面维护复审'")
    text = text.replace("# 复用GPU模板留下旧文件名，实际首刀范围由物理输入SHA和目录绑定。", "# 各组固定同一首刀物理源，仅GPU目标面数不同；维护协议保持。").replace("'薄壁首刀最低SDF分辨率256完整输出的同源整面维护复审'", "'薄壁同源简化预算输出的同协议整面维护复审'")
    name = "audit_thin_budget_maintenance.py"
    (here / name).write_text(text, "utf8")
    output = here.parent / "Geogram与PaMO切削排斥冻结_20261005_薄壁预算输出整面复审"
    output.mkdir(exist_ok=False)
    (output / name).write_text(text, "utf8")
    (output / "01-执行源码冻结清单.json").write_text(json.dumps([{"file": name, "sha256": hashlib.sha256((output / name).read_bytes()).hexdigest()}], ensure_ascii=False, indent=2), "utf8")
    print(output, flush=True)


if __name__ == "__main__":
    main()
