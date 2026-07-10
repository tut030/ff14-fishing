"""存档模块校验 (Step 4)  —  python3 tests/test_save.py"""

from engine import save as S


def test_save():
    slot = "_test_save"
    p = S._path(slot)
    bak = p.with_suffix(".json.bak")
    for f in (p, bak):
        if f.exists():
            f.unlink()

    # 1) 首存: 文件出现, 内容能读回
    st = S.new_state()
    st["gil"] = 100
    S.save(st, slot)
    assert S.load(slot)["gil"] == 100

    # 2) 二存: 生成 .bak, 且 .bak 是上一版(gil=100)
    st["gil"] = 250
    S.save(st, slot)
    assert bak.exists()
    import json
    assert json.loads(bak.read_text(encoding="utf-8"))["gil"] == 100
    assert S.load(slot)["gil"] == 250

    # 3) 回滚: 把 .bak 恢复成当前
    assert S.restore_backup(slot) is True
    assert S.load(slot)["gil"] == 100

    # 4) 防目录穿越: 恶意档名也只会落在 saves/ 内
    evil = S._path("../../etc/passwd")
    assert S.SAVES_DIR in evil.resolve().parents
    assert "/" not in evil.name and "\\" not in evil.name

    # 清理
    for f in (p, bak, p.with_suffix(".json.tmp")):
        if f.exists():
            f.unlink()


