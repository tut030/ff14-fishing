"""英文输出模式(lang en) 校验"""
from engine import i18n
from engine.game import Game
from engine import save as S

T = 1_700_000_000


def _fresh(slot):
    g = Game(slot=slot, fixed_time=T)
    g.state = S.new_state()
    g.state["seed"] = 4
    return g


def test_translate_core_phrases():
    assert "Cast... waiting" in i18n.translate("🎣 抛竿入水…静候 5s…")
    assert "HOOKSET WINDOW" in i18n.translate("⚔ 提钩窗口! 下一条命令定生死:")
    assert "Guide 2/1445" in i18n.translate("图鉴 2/1445")


def test_lang_toggle_persists_and_translates():
    g = _fresh("_t_i18n")
    out = g.cmd("lang en")
    assert "English" in out
    assert g.state["lang"] == "en"
    out = g.cmd("cast")
    assert ("Cast... waiting" in out) or ("no bite" in out) or ("nothing is biting" in out)
    assert "Guide " in out                    # 状态栏
    assert "抛竿入水" not in out
    helped = g.cmd("help")
    assert "Commands:" in helped
    out2 = g.cmd("lang cn")
    assert g.state.get("lang") is None
    assert "抛竿" in g.cmd("help")


def test_flavor_en_used_when_available():
    g = _fresh("_t_i18n2")
    g.cmd("lang en")
    out = g.cmd("status Cupfish")             # 鱼大叔: 自带 flavor_en
    assert "leisurely" in out or "sunlight" in out
