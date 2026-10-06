"""从已保存的阻断输入验证串联修复入口，不覆盖历史独立操作记录。"""

from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import numpy as np
import trimesh
from fragment_pipeline import repair_input
from locality_masks import save_obj_fp64
from audit_followup_candidate import sha256


def main():
    here = Path(__file__).resolve().parent
    batch = here / "实验结果/20261004_局部维护六路线C1开发_清理与复用"
    old = json.loads((batch / "01-局部C1逐帧执行与独立审计.json").read_text(encoding="utf-8"))
    output = here / "实验结果/20261004_串联碎片修复开发"
    output.mkdir(exist_ok=False)
    report = {"time_beijing": datetime.now(timezone(timedelta(hours=8))).isoformat(), "rows": [],
              "code_sha256": {name: sha256(here / name) for name in ("fragment_pipeline.py", "locality_retriangulate.py", "locality_sliver_collapse.py")},
              "scope": "已见阻断输入；独立CPU入口审计，非新的连续成功声明"}
    for row in old["rows"]:
        if row["status"] != "retained_parent_and_stopped":
            continue
        case = row["route"] + "_" + row["event"]
        inputs = batch / case
        source = trimesh.load(inputs / "source_clean.obj", force="mesh", process=False)
        bits = np.array(json.loads((inputs / "labels_clean.json").read_text())["operand_bits"])
        result, labels, details = repair_input(source, bits)
        path = output / (case + ".obj")
        save_obj_fp64(result, path)
        report["rows"].append({"case": case, "source_sha256": sha256(inputs / "source_clean.obj"),
                               "output_sha256": sha256(path), "labels": labels.tolist(), "repair": details})
        (output / "01-串联碎片修复记录.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(case, details["accepted"], details["initial_invalid_faces"], details["remaining_invalid_faces"], flush=True)
    report["status"] = "completed"
    (output / "01-串联碎片修复记录.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
