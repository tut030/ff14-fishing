"""一键打发布包 —— 根治"zip 里混进测试存档 / 内部文档"的问题。

用法(项目根目录或任意位置均可):
    python tools/make_release.py v43.2        # 公开包(默认, 发 Release 用)
    → ff14-fishing-v43.2-full.zip             #   不含 docs/ 内部文档
    python tools/make_release.py v43.2 dev    # 内部交接包(发给克克/AI 联合开发用)
    → ff14-fishing-v43.2-dev.zip              #   含 docs/, 切勿公开上传!

自动排除(两种模式都排):
  - saves/  下除 .gitkeep 外的一切(玩家档 / 测试残留不进包)
  - __pycache__/ 与 *.pyc、.pytest_cache/、.git/、ff14_fishing_home/
  - 项目根目录已有的 *.zip(旧发布包不套娃)
公开包额外排除并自检:
  - docs/ 内部设计文档 —— 包里若出现 docs/ 会自检失败、删除半成品包。

安全说明: 纯标准库、不联网、不读写项目目录以外的任何路径、
不涉及任何密钥或凭据; 输出只有根目录下一个 zip 文件。
"""
from __future__ import annotations
import sys
import zipfile
from pathlib import Path

EXCLUDE_DIRS = {".git", "__pycache__", ".pytest_cache", "ff14_fishing_home"}


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0
    ver = sys.argv[1].lstrip("vV")
    dev = len(sys.argv) > 2 and sys.argv[2].lower() == "dev"
    root = Path(__file__).resolve().parent.parent      # tools/ 的母目录 = 项目根
    top = f"ff14-fishing-v{ver}"
    out = root / f"{top}-{'dev' if dev else 'full'}.zip"
    exclude = set(EXCLUDE_DIRS) | (set() if dev else {"docs"})

    picked, skipped = [], 0
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if (set(rel.parts) & exclude or p.suffix in (".pyc", ".zip")
                or (rel.parts[0] == "saves" and rel.name != ".gitkeep")):
            skipped += 1
            continue
        picked.append(rel)

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in picked:
            z.write(root / rel, f"{top}/{rel.as_posix()}")

    # ── 自检: 包里不允许出现的东西, 出现即报错并删除半成品 ──
    with zipfile.ZipFile(out) as z:
        names = z.namelist()
    bad = [n for n in names
           if "__pycache__" in n or n.endswith(".pyc")
           or ("/saves/" in n and not n.endswith(".gitkeep"))
           or "ff14_fishing_home" in n
           or (not dev and "/docs/" in n)]
    if bad:
        out.unlink()
        print("❌ 自检失败, 已删除半成品包:", bad[:5])
        return 1

    kb = out.stat().st_size / 1024
    kind = "内部交接包(含 docs, 只发给克克!)" if dev else "公开包(不含 docs, 可挂 Release)"
    print(f"✅ {out.name}: {kind}")
    print(f"   {len(picked)} 个文件, {kb:.0f} KB (排除 {skipped} 项; 自检通过)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
