"""固定独立符号诊断，仅改变PaMO作者公开的面数比例参数。"""

import argparse
import sys

from pamo import PaMO

import stage2_capture_probe


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--ratio", type=float, required=True)
    args, remaining = parser.parse_known_args()
    original_run = PaMO.run

    def run_with_ratio(self, points, triangles, ratio, *positional, **keywords):
        # 其余运行参数仍由原诊断脚本及作者实现决定。
        return original_run(self, points, triangles, args.ratio, *positional, **keywords)

    PaMO.run = run_with_ratio
    sys.argv = [sys.argv[0], *remaining]
    try:
        stage2_capture_probe.main()
    finally:
        PaMO.run = original_run


if __name__ == "__main__":
    main()
