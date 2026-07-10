"""pytest 配置: 自动把项目根目录加入 sys.path, 各测试文件不用重复写。"""
import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
