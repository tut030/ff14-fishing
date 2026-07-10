"""路遇小事件(v23·方案A) 测试。"""
import random

import pytest

from engine import encounters as enc


@pytest.fixture
def always(monkeypatch):
    """把触发概率临时调成 100%, 便于确定性测试。"""
    monkeypatch.setattr(enc, "CHANCE", 2.0)


def _state(**kw):
    s = {"gil": 0, "gp": 100, "level": 5, "xp": 0}
    s.update(kw)
    return s


def test_off_switch_blocks(always):
    s = _state(enc_off=True)
    assert enc.roll(s, random.Random(1), now=1000.0) == ""


def test_cooldown_blocks(always):
    s = _state(enc_at=1000.0)
    assert enc.roll(s, random.Random(1), now=1000.0 + enc.COOLDOWN - 1) == ""
    assert enc.roll(s, random.Random(1), now=1000.0 + enc.COOLDOWN + 1) != ""


def test_triggers_and_rewards(always):
    reward = 0
    for seed in range(60):
        s = _state()
        txt = enc.roll(s, random.Random(seed), now=10000.0 + seed * 999)
        assert txt, "概率100%下必定触发"
        assert s["enc_count"] == 1 and s["enc_at"] > 0
        assert "{item}" not in txt and "{npc}" not in txt
        if (s["gil"] > 0 or s["xp"] > 0 or s["gp"] > 100
                or s.get("keepsakes") or s.get("bait_stock")):
            reward += 1
    assert reward > 40      # 绝大多数事件有实际奖励(bait_gift无饵时空效果)


def test_keepsake_collected(always):
    for seed in range(200):
        s = _state()
        enc.roll(s, random.Random(seed), now=50000.0)
        if s.get("keepsakes"):
            assert s["keepsakes"][0] in enc._KEEPSAKES
            assert "_enc_item" not in s          # 临时键要清理干净
            return
    raise AssertionError("200 个种子里应至少抽中一次纪念小物")


def test_default_chance_reasonable():
    """默认概率下 2000 次 goto 的触发率应在 15%±5% 内。"""
    hits = 0
    for seed in range(2000):
        s = _state()
        if enc.roll(s, random.Random(seed), now=90000.0):
            hits += 1
    assert 0.10 < hits / 2000 < 0.20


def test_toggle_roundtrip():
    s = _state()
    assert "关闭" in enc.toggle(s, "off") and s["enc_off"] is True
    assert enc.roll(s, random.Random(1), now=1.0) == ""
    assert "打开" in enc.toggle(s, "on") and s["enc_off"] is False
    assert "路遇小事件" in enc.toggle(s, "")


def test_text_style_rules():
    """文案规范: 禁用字词不得出现; 称谓只用白名单。"""
    banned = ["其他", "少女", "少男", "兄弟"]
    pool_text = "".join(ev["text"] for ev in enc._EVENTS)
    pool_text += "".join(enc._KEEPSAKES)
    for w in banned:
        assert w not in pool_text, f"文案池出现禁用词: {w}"
    assert "他" not in pool_text.replace("其它", ""), "文案池不用第三人称男性代词"
    for ev in enc._EVENTS:
        for r in (ev["role"] or []):
            assert r in enc._R_ANY, f"称谓越出白名单: {r}"
