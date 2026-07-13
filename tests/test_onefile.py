"""单文件版构建自检 —— 打包→在干净临时目录里跑通 look + export。"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import build_onefile  # noqa: E402


def _run(f: Path, cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(f), *args],
                          capture_output=True, text=True,
                          cwd=cwd, timeout=180)


def test_build_and_play(tmp_path):
    out = tmp_path / "ff14_fishing.py"
    info = build_onefile.build(out)
    assert info["files"] > 40, "引擎+数据应该都进包"

    r = _run(out, tmp_path, "_t", "look")
    assert r.returncode == 0 and "📍" in r.stdout, r.stdout + r.stderr

    # 解包目录与存档就位, 且再跑一次不重复解包(版本戳生效)
    home = tmp_path / "ff14_fishing_home"
    assert (home / "engine" / "game.py").exists()
    assert (home / "saves" / "_t.json").exists()
    assert (home / ".pkg_version").read_text(encoding="utf-8").strip() == info["version"]

    r2 = _run(out, tmp_path, "_t", "export")
    assert r2.returncode == 0 and "FF14FISH1." in r2.stdout, r2.stdout + r2.stderr
