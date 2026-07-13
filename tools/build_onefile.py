"""一键打「单文件随身版」—— 生成零依赖的 ff14_fishing.py。

用法(项目根目录或任意位置均可):
    python tools/build_onefile.py
    → 在项目根目录生成 ff14_fishing.py(版本号自动取自 CHANGELOG.md 顶部)

它是什么:
  把 engine/ 全部模块 + data/ 全部数据 + 三份 AI 说明书 + LICENSE
  压缩后嵌进一个 .py 文件。把这一个文件传给能跑代码的 AI 就能玩:
      import ff14_fishing as g; print(g.cmd("look"))
  首次运行会在文件旁解出 ff14_fishing_home/(引擎+数据+存档目录);
  版本升级重解引擎与数据, 但绝不触碰 saves/ 里的玩家档。

安全说明: 纯标准库、不联网、不读写项目目录以外的任何路径、
不涉及任何密钥或凭据; 自检在系统临时目录里进行, 不弄脏项目。
"""
from __future__ import annotations

import base64
import io
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent      # tools/ 的母目录 = 项目根
OUT_NAME = "ff14_fishing.py"
_STAMP = (2026, 1, 1, 0, 0, 0)                     # 固定时间戳 → 构建可复现
_WRAP = 120                                        # base64 折行宽度

# 进包清单: (glob 所在目录, 通配) —— 顺序固定、逐个排序, 保证包字节稳定
_PACK_GLOBS = [("engine", "*.py"), ("data", "*.json")]
_PACK_FILES = ["AI_GUIDE_MINI.md", "AI_GUIDE.md", "AI_GUIDE_EN.md", "LICENSE"]


def _read_version() -> str:
    """从 CHANGELOG.md 顶部的 `## vX.Y` 取版本号, 打包不用手改两处。"""
    m = re.search(r"^## v([\w.\-]+)", (ROOT / "CHANGELOG.md").read_text(
        encoding="utf-8"), re.MULTILINE)
    return m.group(1) if m else "0"


def _collect() -> list[tuple[str, bytes]]:
    items: list[tuple[str, bytes]] = []
    for sub, pat in _PACK_GLOBS:
        for p in sorted((ROOT / sub).glob(pat)):
            items.append((f"{sub}/{p.name}", p.read_bytes()))
    for name in _PACK_FILES:
        p = ROOT / name
        if p.exists():
            items.append((name, p.read_bytes()))
    return items


def _make_zip(items: list[tuple[str, bytes]]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, data in items:
            info = zipfile.ZipInfo(name, date_time=_STAMP)
            info.external_attr = 0o644 << 16
            z.writestr(info, data, zipfile.ZIP_DEFLATED, compresslevel=9)
    return buf.getvalue()


_TEMPLATE = '''#!/usr/bin/env python3
"""🎣 FF14 钓鱼 · 单文件随身版 v@VERSION@ (真实引擎, 非模拟)
============================================================
完整仓库自动打包成的一个文件: 引擎 + 全部数据都在里面, 零依赖,
Python 3.10+ 直接跑。给能执行代码的 AI 玩家用——收到这一个文件就能玩。

用法(import, 推荐给 AI):
    import ff14_fishing as g
    print(g.cmd("look"))                    # 默认玩家 default
    print(g.cmd("cast 10; sell all; look", player="sakura"))
    print(g.guide())                        # 读速通说明书(先读这个!)

用法(命令行):
    python ff14_fishing.py <玩家名> "<命令>"
    python ff14_fishing.py sakura "cast 10; goto Costa del Sol; look"

存档:
    首次运行在本文件旁边解出 ff14_fishing_home/(引擎+数据),
    进度在 ff14_fishing_home/saves/<玩家名>.json, 自动保存自动备份。
    ⚠ 运行环境每次对话会清空文件? 离开前发 `export` 拿到「存档串」
    交给玩家保存; 下次 `import <存档串>` 原地恢复, 一条鱼都不丢。

完整仓库: https://github.com/tut030/ff14-fishing  ·  MIT License
本文件由 tools/build_onefile.py 生成, 请勿手改。
"""
from __future__ import annotations

import base64
import io
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

VERSION = "@VERSION@"

_PKG_B64 = """
@B64@
"""


def _home() -> Path:
    """解包目录: 优先放在本文件旁边; 只读环境退回工作目录/临时目录。"""
    candidates = [Path(__file__).resolve().parent, Path.cwd(),
                  Path(tempfile.gettempdir())]
    for base in candidates:
        d = base / "ff14_fishing_home"
        try:
            d.mkdir(exist_ok=True)
            probe = d / ".write_test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            return d
        except OSError:
            continue
    raise SystemExit("[单文件版] 找不到可写目录来解包引擎。")


def _ensure() -> Path:
    home = _home()
    ver_file = home / ".pkg_version"
    fresh = not (ver_file.exists()
                 and ver_file.read_text(encoding="utf-8").strip() == VERSION)
    if fresh:
        # 版本变化: 重解 engine/ 与 data/(先清掉旧的, 防残留模块捣乱);
        # saves/ 永远不碰——玩家档比什么都金贵。
        for sub in ("engine", "data"):
            shutil.rmtree(home / sub, ignore_errors=True)
        data = base64.b64decode("".join(_PKG_B64.split()))
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for info in z.infolist():
                name = info.filename
                if ".." in name or name.startswith(("/", "\\\\")):
                    continue                     # 防路径穿越(双保险)
                ok = (name.startswith(("engine/", "data/"))
                      or name in ("AI_GUIDE_MINI.md", "AI_GUIDE.md",
                                  "AI_GUIDE_EN.md", "LICENSE"))
                if not ok:
                    continue
                target = home / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(z.read(info))
        (home / "saves").mkdir(exist_ok=True)
        ver_file.write_text(VERSION, encoding="utf-8")
    if str(home) not in sys.path:
        sys.path.insert(0, str(home))
    return home


_HOME = _ensure()
from engine.game import Game, cmd as _engine_cmd   # noqa: E402


def cmd(text: str, player: str = "default") -> str:
    """给 AI 的便捷入口: 一次调用 = 一条命令 + 一段回复, 进度自动存。"""
    return _engine_cmd(text, slot=player)


def guide() -> str:
    """速通说明书(约 1500 字, 建议开玩前先读这份)。"""
    return (_HOME / "AI_GUIDE_MINI.md").read_text(encoding="utf-8")


def main() -> int:
    if (getattr(sys.stdout, "encoding", "") or "").lower() not in ("utf-8", "utf8"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")   # Windows 控制台防乱码
        except Exception:
            pass
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    player = args[0]
    command = " ".join(args[1:]).strip() or "look"
    try:
        print(Game(slot=player).cmd(command))
        return 0
    except BrokenPipeError:
        return 0
    except Exception as e:
        try:
            print(f"[出错] {type(e).__name__}: {e}")
        except BrokenPipeError:
            pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
'''


def build(out_path: Path, version: str | None = None) -> dict:
    """生成单文件版, 返回 {'files': N, 'kb': 大小, 'version': v}。"""
    version = version or _read_version()
    items = _collect()
    b64 = base64.b64encode(_make_zip(items)).decode("ascii")
    wrapped = "\n".join(b64[i:i + _WRAP] for i in range(0, len(b64), _WRAP))
    src = (_TEMPLATE.replace("@VERSION@", version)
                    .replace("@B64@", wrapped))
    out_path.write_text(src, encoding="utf-8")
    return {"files": len(items), "kb": out_path.stat().st_size / 1024,
            "version": version}


def _self_check(built: Path) -> bool:
    """在系统临时目录里复制一份实际跑一遍 look, 确认能开箱即玩。"""
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / built.name
        f.write_bytes(built.read_bytes())
        r = subprocess.run([sys.executable, str(f), "_selfcheck", "look"],
                           capture_output=True, text=True, cwd=td, timeout=180)
        ok = (r.returncode == 0 and "📍" in r.stdout)
        if not ok:
            print("❌ 自检失败, 输出如下:\n", r.stdout[-800:], r.stderr[-800:])
        return ok


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0
    out = ROOT / OUT_NAME
    info = build(out)
    if not _self_check(out):
        return 1
    print(f"✅ {OUT_NAME}: v{info['version']}, 打入 {info['files']} 个文件, "
          f"共 {info['kb']:.0f} KB(自检通过: 临时目录里开箱跑通 look)")
    print("   把这一个文件传给能跑代码的 AI 即可开玩; "
          "引擎/数据有改动后重跑本脚本再提交。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
