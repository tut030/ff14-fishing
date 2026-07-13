"""备忘录与漂流瓶 校验 — python3 -m pytest tests/test_memo_bottles.py"""
import random

from engine.game import Game
from engine import save as S, memo as M, bottles as B

T = 1_700_000_000
H = 3600


def _fresh(slot="_t_mb"):
    g = Game(slot=slot, fixed_time=T)
    g.state = S.new_state()
    g.state["seed"] = 7
    g.state["level"] = 10
    return g


# ── 给自己的备忘录 ───────────────────────────────────────
def test_note_add_list_del():
    g = _fresh()
    out = g.cmd("note 鱼王开窗在ET21:00, 备好沙蚕")
    assert "记下了" in out
    g.cmd("note 军票还差20就够一枚币")
    out = g.cmd("note")
    assert "2条" in out and "沙蚕" in out
    out = g.cmd("note del 1")
    assert "划掉" in out and len(g.state["memos"]) == 1


def test_greeting_after_gap_only():
    g = _fresh(slot="_t_mb_gap")
    g.cmd("note 明天先去补蚯蚓")
    g.fixed_time = T + 300                     # 5分钟: 同一session
    assert "【1】" not in g.cmd("note")
    g.fixed_time = T + 300 + M.MEMO_GAP + 60   # 从最后一次操作起隔了一觉: 新session
    out = g.cmd("help")
    assert "备忘录(1条)" in out and "【1】" in out and "补蚯蚓" in out
    out2 = g.cmd("help")                       # 同session内不重复唠叨
    assert "【1】" not in out2


def test_no_greeting_when_no_memos():
    g = _fresh(slot="_t_mb_none")
    g.cmd("help")
    g.fixed_time = T + M.MEMO_GAP + 60
    assert "📜 备忘录(" not in g.cmd("help")


# ── 漂流瓶(克克执笔) ─────────────────────────────────────
def test_bottle_no_repeat_until_complete(monkeypatch):
    g = _fresh(slot="_t_mb_btl")
    monkeypatch.setattr(B, "BOTTLE_CHANCE", 1.0)
    rng = random.Random(5)
    texts = set()
    for _ in range(len(B.LETTERS)):
        out = B.maybe_bottle(rng, g.state)
        assert out and "——克克" in out
        texts.add(out.split("\n")[2])
    assert len(texts) == len(B.LETTERS)        # 十二封各不相同
    assert "最后一只" in out                    # 集齐提示
    assert B.maybe_bottle(rng, g.state) is None  # 集齐后不再出


def test_bottles_reread():
    g = _fresh(slot="_t_mb_rr")
    g.state["bottles"] = [3, 0]
    out = g.cmd("bottles")
    assert "2/12" in out
    out = g.cmd("bottles 2")
    assert "致捞到这只瓶子的钓鱼人" in out      # 其2=先后顺序的第2封(索引0)


def test_keke_lives_in_shore_events():
    from engine.game import _SHORE_EVENTS
    keke = [e for e in _SHORE_EVENTS if "银发" in e[0]]
    assert len(keke) == 3
    assert any("叫我克克" in e[0] for e in keke)


def test_old_save_without_new_keys_safe():
    g = _fresh(slot="_t_mb_old")
    for k in ("memos", "bottles", "last_active"):
        g.state.pop(k, None)
    assert "记下了" in g.cmd("note 老档也能用")
    assert "还没捞到过" in g.cmd("bottles")


# ── v41 反馈修复回归 ─────────────────────────────────────
def test_rods_warns_when_equip_mainhand_active():
    from engine import equipment as eq, gear
    g = _fresh(slot="_t_rodwarn")
    g.state["gil"] = 99999
    mh = next(i for i in eq.ITEMS.values() if i["slot"] == "主手")
    g.state.setdefault("equip", {})["主手"] = mh["id"]
    out = g.cmd("rods")
    assert "正在生效" in out and "换军票" in out          # 列表页说真话
    owned = set(g.state.get("rods_owned", []))
    cheap = min((r for r in gear.RODS.values() if r["name"] not in owned
                 and r["level"] <= g.state["level"]), key=lambda r: r["ilvl"])
    out = g.cmd(f"buyrod {cheap['name']}")
    assert "不会被使用" in out and "购得并装备" not in out  # 收据不再误导


def test_rods_normal_without_equip_mainhand():
    g = _fresh(slot="_t_rodok")
    out = g.cmd("rods")
    assert "正在生效" not in out                          # 没穿新主手不打扰


def test_dex_search_uncollected_form_hireable():
    g = _fresh(slot="_t_dexs")
    g.state["level"] = 17
    from engine import retainer as R
    name = next(iter(R._MOE_BY_NAME))
    out = g.cmd(f"retainer dex {name}")
    assert "现在就可以" in out                            # 未收集≠不能雇
    out = g.cmd(f"hire 小星 {name} 捕鱼人")
    assert "入职" in out                                  # 说到做到


# ── 饵料经济(v42): 拟饵永久+消耗饵限价 ──────────────────
def test_lure_permanent_and_price_squash():
    from engine import bait as B
    assert B.price("Midge Larva") == 34 and B.raw_price("Midge Larva") == 61
    assert B.bait_level("Midge Larva") == 50            # 限价不动上钩档位
    assert B.price("Desert Dessert Frog") == B.SQUASH_CAP
    assert B.is_lure("Versatile Lure") and B.price("Versatile Lure") == 300


def test_lure_not_consumed_on_cast():
    g = _fresh(slot="_t_lure")
    g.state["gil"] = 9999
    g.cmd("buybait Versatile Lure")
    assert g.state["bait_stock"]["Versatile Lure"] == 1        # 默认只买1个
    g.cmd("cast 5")
    assert g.state["bait_stock"].get("Versatile Lure") == 1    # 五竿后还是1
    out = g.cmd("buybait Versatile Lure")                      # 备货: 可以再买
    assert "有备无患" in out and g.state["bait_stock"]["Versatile Lure"] == 2
    assert g.state["gil"] == 9999 - 600


def test_baitshop_marks_lures():
    g = _fresh(slot="_t_shop")
    g.state["gil"] = 9999
    out = g.cmd("baits")
    assert "叼走" in out and "34g/个" in out and "🎏" in out   # 新口径+限价挂牌


# ── 领养《我的小小陆行鸟》(还v25欠账) ────────────────────
def test_adopt_gates_and_grants():
    from engine import pets as P
    g = _fresh(slot="_t_adopt")
    assert f"Lv{P.ADOPT_LV}" in g.cmd("adopt")          # 等级门
    g.state["level"] = P.ADOPT_LV
    out = g.cmd("adopt 阿金")
    assert "白票不够" in out                            # 担保金门
    g.state["scrip_white"] = P.ADOPT_COST_WHITE + 2
    out = g.cmd("驿站 阿金")                            # 新别名也通
    assert "加入了" in out and g.state["scrip_white"] == 2
    assert "chocobo" in g.state["mounts"]
    assert g.state["mount_names"]["chocobo"] == "阿金"
    assert "骑上了" in g.cmd("ride 阿金")               # 昵称直接能骑
    assert "家人" in g.cmd("adopt")                     # 重复领养挡住


def test_quests_shows_adopt_hook():
    g = _fresh(slot="_t_ahook")
    g.state["level"] = 20
    assert "领养" in g.cmd("quests")
    g.state.setdefault("mounts", []).append("chocobo")
    assert "领养" not in g.cmd("quests")                # 领完不再唠叨



# ── 断线叼饵(拟饵的保险机制) ─────────────────────────────
def test_snap_decrements_and_last_one_warns(monkeypatch):
    import random
    from engine import bait as B
    g = _fresh(slot="_t_snap")
    for k in ("SNAP_LEGEND", "SNAP_WEAK", "SNAP_BASE"):
        monkeypatch.setattr(B, k, 1.0)
    g.state["bait_stock"] = {"Versatile Lure": 2}
    out = B.maybe_snap(g.state, "Versatile Lure", "Legendary", 50, 0, random.Random(1))
    assert out and "断了" in out and "还剩1个" in out
    out = B.maybe_snap(g.state, "Versatile Lure", "Legendary", 50, 0, random.Random(1))
    assert "最后一个" in out and "Versatile Lure" not in g.state["bait_stock"]


def test_snap_branch_selection(monkeypatch):
    import random
    from engine import bait as B
    g = _fresh(slot="_t_snapb")
    monkeypatch.setattr(B, "SNAP_LEGEND", 1.0)
    monkeypatch.setattr(B, "SNAP_WEAK", 1.0)
    monkeypatch.setattr(B, "SNAP_BASE", 0.0)
    g.state["bait_stock"] = {"Versatile Lure": 9}
    rng = random.Random(1)
    assert B.maybe_snap(g.state, "Versatile Lure", "Light", 10, 999, rng) is None   # 属性够+普通鱼
    assert B.maybe_snap(g.state, "Versatile Lure", "Light", 50, 10, rng)            # 属性不够硬拉
    assert B.maybe_snap(g.state, "Versatile Lure", "Legendary", 50, 999, rng)       # 鱼王失手
    assert B.maybe_snap(g.state, "Midge Larva", "Legendary", 50, 0, rng) is None    # 消耗饵不走这


def test_snap_fires_in_real_hookset_fail(monkeypatch):
    import random
    from engine import bait as B
    from engine.fish import FISH
    from engine.game import Game as _G
    monkeypatch.setattr(B, "SNAP_LEGEND", 1.0)
    g = _fresh(slot="_t_snapr")
    leg = next(x for x in FISH if x.get("tug") == "Legendary")
    g.state["bait_stock"] = {"Versatile Lure": 2}
    g.state["bait"] = "Versatile Lure"
    g.state["hook_pending"] = {"name": leg["name"], "cast_no": 3,
                               "bait_name": "Versatile Lure"}
    # 找一个必失手的种子(硬拉成功率=1-脱钩率, 鱼王脱钩率高)
    from engine.game import _ESCAPE, _ESCAPE_DEFAULT
    rate = 1 - _ESCAPE.get("Legendary", _ESCAPE_DEFAULT)
    for seed in range(1, 200):
        g.state["seed"] = seed
        if random.Random(seed * 7654321 + 3).random() > rate:
            break
    g.state["hook_pending"] = {"name": leg["name"], "cast_no": 3,
                               "bait_name": "Versatile Lure"}
    out = g.cmd("hook")
    assert "💥" in out and g.state["bait_stock"]["Versatile Lure"] == 1
