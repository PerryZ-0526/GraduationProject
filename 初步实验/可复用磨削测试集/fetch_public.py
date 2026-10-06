"""保存BodyParts3D官方原始包、许可和器官表，按名称选择骨模型。"""

from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import urllib.request
import zipfile


HERE = Path(__file__).resolve().parent
BASE = "https://dbarchive.biosciencedbc.jp/data/bodyparts3d/LATEST/"


def main():
    root = HERE / "公开输入_BodyParts3D_v4"
    raw = root / "原始资料"
    raw.mkdir(parents=True, exist_ok=True)
    files = ("README_e.html", "isa_parts_list_e.txt", "isa_element_parts.txt", "isa_BP3D_4.0_obj_99.zip")
    records = []
    for name in files:
        path = raw / name
        if not path.exists():
            temporary = path.with_suffix(path.suffix + ".partial")
            with urllib.request.urlopen(BASE + name, timeout=60) as response, temporary.open("wb") as stream:
                while block := response.read(1024 * 1024):
                    stream.write(block)
            if name.endswith(".zip"):
                with zipfile.ZipFile(temporary) as archive:
                    if archive.testzip() is not None:
                        raise ValueError("公开包CRC校验失败")
            temporary.replace(path)
        records.append({"file": str(path.relative_to(root)), "url": BASE + name,
                        "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        print(name, path.stat().st_size, flush=True)
    # 保留官方映射行与原OBJ；不自动封洞、缩放或宣布临床单位。
    selected = [line for line in (raw / "isa_element_parts.txt").read_text(encoding="utf-8-sig").splitlines()
                if any(term in line.lower() for term in ("scapula", "humerus", "femur", "tibia"))]
    extracted = []
    destination = root / "骨模型原件"
    destination.mkdir(exist_ok=True)
    with zipfile.ZipFile(raw / files[-1]) as archive:
        names = {Path(name).stem: name for name in archive.namelist() if name.endswith(".obj")}
        for line in selected:
            for token in line.split("\t"):
                token = token.strip().removesuffix(".obj")
                if token in names and token not in {r["id"] for r in extracted}:
                    content = archive.read(names[token])
                    (destination / (token + ".obj")).write_bytes(content)
                    extracted.append({"id": token, "mapping_line": line, "archive_member": names[token],
                                      "file": "骨模型原件/" + token + ".obj", "sha256": hashlib.sha256(content).hexdigest(),
                                      "split": "public_application_same_atlas"})
    result = {"time_beijing": datetime.now(timezone(timedelta(hours=8))).isoformat(), "release": "4.0",
              "license": "CC Attribution 4.0 International", "license_url": "https://dbarchive.biosciencedbc.jp/en/bodyparts3d/lic.html",
              "attribution": "BodyParts3D, © The Database Center for Life Science licensed under CC Attribution 4.0 International",
              "units": "所读官方README未声明坐标单位；原坐标保留，应用前显式声明测试尺度",
              "scope": "成人男性解剖图谱的减面网格；非多个独立患者，非原始CT",
              "downloads": records, "models": extracted}
    (root / "01-公开来源清单.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("selected_models", len(extracted), flush=True)


if __name__ == "__main__":
    main()
