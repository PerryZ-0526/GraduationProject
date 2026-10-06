"""顺序修复保留12路线持续复用相同的完整几何与接触资产检查。"""
from pathlib import Path
import unittest
import test_initial_encoding_holdout as original


if __name__=='__main__':
    # 仅选择新的完整资产包；原三项几何、分母和物理接触检查不改变。
    original.ROOT=Path(__file__).resolve().parent/'清理顺序新参数保留12路线_v2'
    unittest.main(module=original)
