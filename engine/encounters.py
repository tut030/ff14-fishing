"""
FF14 钓鱼 路遇小事件 —— goto 赶路途中的自动风味事件 (v23)
------------------------------------------------------------
定位: 与岸钓偶遇(_SHORE_EVENTS, 蹲点时触发)互补, 本模块只在
"赶路"(goto 成功移动)时低概率触发, 主题是路上的互助与拾遗。

方案 A · 全自动: 播 2~4 行小故事, 奖励自动结算, 不打断批量连招。
文案与 i18n: 属风味文本, 按现行设计英文模式下暂留中文。

★ 文案规范(新增条目请遵守) ★
  1. NPC 一律写成「形容词的 + 称谓」, 称谓只用 _ROLES 白名单;
  2. 不用第三人称代词(用"对方"或复述称谓), 不出现禁用字词;
  3. 互助平视、不写成施舍; 不用失踪儿童类桥段; 不做外貌评判。
"""

from __future__ import annotations
import random

# ===== 可调常量 =============================================
CHANCE = 0.15          # 每次 goto 成功移动的触发概率
COOLDOWN = 300         # 两次触发的最小间隔(秒, 现实时间)
# ===========================================================

# ── 称谓白名单 ──────────────────────────────────────────────
_R_KID = ["小孩", "女孩", "男孩"]
_R_ADULT = ["大人", "青年人", "女士", "男士", "青年女子", "青年男子"]
_R_ELDER = ["老人", "老年女子", "老年男子"]
_R_TEEN = ["少年人"]
_R_ANY = _R_KID + _R_ADULT + _R_ELDER + _R_TEEN

# ── 形容词池(按事件情境取用) ────────────────────────────────
_D_NEUTRAL = ["衣着整洁的", "鞋子上沾了泥巴的", "高大的", "挎着菜篮的",
              "晒得黝黑的", "背着鱼篓的", "戴着草帽的"]

# ── 事件池 ──────────────────────────────────────────────────
# 每条: desc=形容词池, role=称谓池, text=模板({npc}/{item}),
#       etype=奖励类型, val=(下限,上限) 或 None
_EVENTS = [
    # —— 帮助类 ——
    dict(desc=["抱着一大摞行李的", "推着小车的"], role=_R_ADULT + _R_ELDER,
         text=("🧺 一位{npc}的行李带断了，东西散了一地。"
               "你蹲下帮忙，一件件捡了回去。\n"
               "   「太感谢了！」对方硬塞给你几枚跑腿钱。"),
         etype="gil", val=(15, 35)),
    dict(desc=["满头大汗的"], role=_R_KID,
         text=("🪁 一位{npc}的风筝挂在了树杈上，急得直转圈。"
               "你用鱼竿轻轻一挑——下来了。\n"
               "   「哇！鱼竿还能这么用！」你今天解锁了鱼竿的第 108 种用法。"),
         etype="xp", val=(10, 20)),
    dict(desc=["迷路的", "风尘仆仆的"], role=_R_ADULT,
         text=("🗺 一位{npc}拿着地图原地打转。"
               "你指了指去主城的路，顺手在地图上画了个小记号。\n"
               "   「原来走反了……」对方道谢后轻快地走了。"),
         etype="xp", val=(8, 15)),
    dict(desc=["拎着两大桶水的"], role=_R_ELDER,
         text=("💧 一位{npc}拎着水桶走走停停。"
               "你搭了把手，一路送到家门口。\n"
               "   临别时被塞了一把晒干的果子。嚼起来意外地香。"),
         etype="gp", val=(20, 40)),
    dict(desc=["受伤的", "虚弱的"], role=_R_ADULT + _R_ELDER,
         text=("🩹 路边一位{npc}扭了脚，正靠着树喘气。"
               "你递过水壶，又帮着把行囊挪到阴凉处。\n"
               "   「歇一会儿就好，谢谢你。」你等对方缓过来才继续赶路。"),
         etype="xp", val=(12, 22)),
    dict(desc=["受到惊吓的"], role=_R_KID,
         text=("🦢 一位{npc}被一只气势汹汹的大鹅追得直跑。"
               "你张开手臂拦住大鹅——对峙三秒，鹅撤了。\n"
               "   「呼……谢谢！」你获得了一个大大的笑容。"),
         etype="xp", val=(8, 15)),
    # —— 拾取类 ——
    dict(desc=None, role=None,
         text=("🪙 路过桥洞时，石缝里闪了一下——一枚旧币。"
               "是谁掉的已经无从考证了。"),
         etype="gil", val=(10, 40)),
    dict(desc=None, role=None,
         text=("✨ 路边有什么东西反着光。捡起来一看——{item}。\n"
               "   没什么用，但很好看。收进了口袋。"),
         etype="keepsake", val=None),
    dict(desc=None, role=None,
         text=("🪱 路边掉着一小包鱼饵，四下无人认领。"
               "看包装还是新的——收下了。"),
         etype="bait_gift", val=(2, 4)),
    # —— 偶遇类 ——
    dict(desc=_D_NEUTRAL, role=_R_ANY,
         text=("💬 同路的一位{npc}闲聊起来：「听说下雨前后，鱼咬钩最欢。」\n"
               "   说完在岔路口挥手作别。"),
         etype="xp", val=(5, 8)),
    dict(desc=_D_NEUTRAL, role=_R_ANY,
         text=("🌾 一位{npc}和你并肩走了一段。谁都没说话，"
               "但夕阳很好，风也很好。\n"
               "   在岔路口互相点头道别。"),
         etype="gp", val=(15, 30)),
]

# 纪念小物池(keepsake)
_KEEPSAKES = [
    "一枚完整的螺旋贝壳",
    "一颗被水磨圆的浅绿色石头",
    "一截缠着水草的漂流木",
    "一张漂流瓶里的纸条：『明天也要加油』",
    "一根不知名鸟儿的蓝色羽毛",
]


def _apply(state: dict, etype: str, val, rng: random.Random,
           now: float | None) -> str:
    """结算奖励, 返回效果尾注(与岸钓偶遇同款格式)。"""
    if etype == "gil":
        n = rng.randint(*val)
        state["gil"] = state.get("gil", 0) + n
        return f"  (+{n} gil)"
    if etype == "xp":
        n = rng.randint(*val)
        from engine import leveling
        leveling.add_xp(state, n)
        return f"  (+{n} xp)"
    if etype == "gp":
        n = rng.randint(*val)
        from engine import gp as gp_mod
        state["gp"] = min(state.get("gp", 0) + n, gp_mod.max_gp(state, now))
        return f"  (+{n} GP)"
    if etype == "bait_gift":
        bt = state.get("bait")
        if not bt:
            return ""
        n = rng.randint(*val)
        from engine import bait as bait_mod
        stock = state.setdefault("bait_stock", {})
        stock[bt] = stock.get(bt, 0) + n
        return f"  (+{n} {bait_mod.disp(bt)})"
    if etype == "keepsake":
        item = rng.choice(_KEEPSAKES)
        ks = state.setdefault("keepsakes", [])
        if item not in ks:
            ks.append(item)
        state["_enc_item"] = item        # 供模板填充
        return ""
    return ""


def roll(state: dict, rng: random.Random,
         now: float | None = None) -> str:
    """goto 成功移动后调用。返回事件文本(带换行)或空串。"""
    if state.get("enc_off"):
        return ""
    if now is not None and now - state.get("enc_at", 0) < COOLDOWN:
        return ""
    if rng.random() > CHANCE:
        return ""
    ev = rng.choice(_EVENTS)
    npc = ""
    if ev["role"]:
        npc = rng.choice(ev["desc"]) + rng.choice(ev["role"])
    effect = _apply(state, ev["etype"], ev["val"], rng, now)
    text = ev["text"].format(npc=npc, item=state.pop("_enc_item", ""))
    if now is not None:
        state["enc_at"] = now
    state["enc_count"] = state.get("enc_count", 0) + 1
    return text + effect + "\n"


def toggle(state: dict, arg: str = "") -> str:
    """encounter [on|off] / 路遇 —— 开关与状态查看。"""
    a = (arg or "").strip().lower()
    if a in ("off", "关", "关闭"):
        state["enc_off"] = True
        return "🚶 路遇小事件已关闭。encounter on 重新打开。"
    if a in ("on", "开", "开启"):
        state["enc_off"] = False
        return "🚶 路遇小事件已打开。赶路时留意路边吧。"
    status = "关闭" if state.get("enc_off") else "开启"
    n = state.get("enc_count", 0)
    ks = state.get("keepsakes", [])
    out = [f"🚶 路遇小事件: {status}中 (goto 赶路时约 15% 触发, 5 分钟冷却)",
           f"   已遇到 {n} 次。encounter on/off 开关。"]
    if ks:
        out.append("   🎁 路上收集的纪念小物: " + "、".join(ks))
    return "\n".join(out)
