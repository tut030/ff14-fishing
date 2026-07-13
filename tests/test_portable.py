"""存档串(export/import)校验 —— python3 -m pytest tests/test_portable.py"""

import re

import pytest

from engine import portable
from engine import save as S
from engine.game import Game

_BLOB_RE = re.compile(r"FF14FISH1\.[A-Za-z0-9+/=\s]+\.[0-9a-f]{8}")


def test_blob_roundtrip_and_paste_tolerance():
    st = S.new_state()
    st["gil"] = 4321
    st["level"] = 7
    blob = portable.export_blob(st)
    assert blob.startswith("FF14FISH1.")

    back = portable.import_blob(blob)
    assert back["gil"] == 4321 and back["level"] == 7

    # 聊天粘贴式: 混入换行/空格/前后闲话, 也要能认出串
    messy = "给你存档~\n " + blob.replace("\n", " \n\t ") + "\n玩得开心!"
    assert portable.import_blob(messy)["gil"] == 4321


def test_blob_rejects_damage():
    blob = portable.export_blob(S.new_state())
    with pytest.raises(portable.BlobError):
        portable.import_blob(blob[:-12])                     # 复制被截断
    with pytest.raises(portable.BlobError):
        portable.import_blob("FF14FISH1.AAAA.00000000")      # 校验不过
    with pytest.raises(portable.BlobError):
        portable.import_blob("随便一段文字")                   # 压根不是串


def test_game_export_import_commands():
    slot = "_test_portable"
    p = S._path(slot)
    stash = p.with_suffix(".pre_import.json")
    for f in (p, p.with_suffix(".json.bak"), p.with_suffix(".json.tmp"), stash):
        if f.exists():
            f.unlink()

    # 1) 玩家 A: 攒点家底, 导出
    g = Game(slot=slot)
    g.state["gil"] = 777
    out = g.cmd("export")
    m = _BLOB_RE.search(out)
    assert m, f"export 输出里没找到存档串: {out[:200]}"
    blob = m.group(0)

    # 2) 假装换了台机器: 删掉档, 新开一局(全新状态)
    p.unlink()
    g2 = Game(slot=slot)
    assert g2.state.get("gil", 0) != 777
    g2._autosave()                    # 让"旧档"落盘, 好验证导入前的保底另存

    # 3) 导入(把 export 整段回复原样粘进来, 验证容错) → 家底回来
    msg = g2.cmd("import " + out)
    assert "导入成功" in msg
    assert Game(slot=slot).state["gil"] == 777
    assert stash.exists(), "导入覆盖前应把当前档另存 .pre_import.json"

    # 4) 坏串导入: 明确报错, 且不动现有进度
    msg2 = g2.cmd("import " + blob[:-10])
    assert "导入失败" in msg2
    assert Game(slot=slot).state["gil"] == 777

    for f in (p, p.with_suffix(".json.bak"), p.with_suffix(".json.tmp"), stash):
        if f.exists():
            f.unlink()
