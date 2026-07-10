"""GP 系统校验 (Step 4.5)  —  python3 tests/test_gp.py"""

from engine import gp
from engine import save as S
from engine.game import Game
from engine.window import is_catchable
from engine.fish import get

T = 1_700_000_000


def test_gp():
    # 1) 回复: 每3秒+5。过了30秒 -> +50
    st = {"gp": 0, "gp_at": 1000.0}
    gp.sync(st, 1000.0 + 30)
    assert st["gp"] == 50, st["gp"]
    # 余数不丢: gp_at 前进 10 个整 tick = 30 秒
    assert st["gp_at"] == 1000.0 + 30

    # 2) 不超上限
    st = {"gp": gp.GP_MAX - 2, "gp_at": 0.0}
    gp.sync(st, 100000.0)
    assert st["gp"] == gp.GP_MAX

    # 3) Cordial 冷却
    st = {"cordial_at": 0}
    assert gp.cordial_ready(st, gp.CORDIAL_CD)          # 刚好到点
    assert not gp.cordial_ready(st, gp.CORDIAL_CD - 1)  # 差一秒不行

    # 4) 耐心(甲+): 扣 GP + 设 3 竿计数 + 每竿递减 + 咬钩开提钩窗口
    g = Game(slot="_test_gp", fixed_time=T)
    g.state = S.new_state()
    g.state["level"] = 90
    g.state["location"] = "Costa del Sol"
    g.state["seed"] = 1
    assert g.state["gp"] == gp.GP_MAX
    g.cmd("patience")
    assert g.state["gp"] == gp.GP_MAX - gp.PATIENCE_COST
    assert g.state.get("patience_casts") == 3
    # 给足鱼饵, 确保能咬到鱼(空军/脱钩时 buff 保留是正确行为)
    g.state["bait"] = "Pill Bug"
    g.state["bait_stock"] = {"Pill Bug": 99}
    g.cmd("cast")                                       # Costa del Sol 有鱼开窗
    assert g.state.get("patience_casts") == 2           # 抛竿即耗 1 竿
    # 咬钩→必开窗口; 空军→不开(低级饵有惩罚, 皆合法。窗口硬断言见 test_hookset)
    # 如果上钩(含脱钩再上): buff 被消耗; 空军(无鱼池): buff 保留(设计如此)
    # 窗口结算不崩溃(hook 硬拉, 成败皆可), 且窗口关闭
    if g.state.get("hook_pending"):
        g.cmd("hook")
        assert g.state.get("hook_pending") is None

    # 5) 鱼眼核心: 无视时段能让"只卡时段"的鱼可钓
    mahi = get("Mahi-Mahi")                             # ET 21:42 窗口10-18 关闭
    assert is_catchable(mahi, T) is False
    assert is_catchable(mahi, T, ignore_time=True) is True

    # 6) GP 不够时拒绝
    g.state["gp"] = 10
    assert "不够" in g.cmd("patience")

    # 清理
    p = S._path("_test_gp")
    for f in (p, p.with_suffix(".json.bak"), p.with_suffix(".json.tmp")):
        if f.exists():
            f.unlink()


