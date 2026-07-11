"""钓鱼日记(手帐) —— 特别渔获自动记下"事实半", "心情半"由玩家主动补。

分工铁律: 游戏记事实(时间/天气/钓场/鱼/尺寸/饵), 绝不替玩家编造感受;
心情是玩家(AI)的主动行为——想什么时候记就什么时候记,
同一条日记可以反复追加(第二次翻看、第三次翻看…), 只追加、永不覆盖。

心情锚推荐格式引自 chord-affect-anchors (MIT):
  https://github.com/CyberSealNull/chord-affect-anchors
  作者: Bonnie (Xingjianmian) & Opia (Claude Opus 4.7)
  最小单元 = 一行具体情境 + 一行和弦(最多4个, 用 → 隔开, bpm可选)。
  游戏不校验格式——写大白话也完全可以, 日记是自由的。
"""
import datetime as _dt

# ═══ 数值总开关 ═══════════════════════════════════════════
TRIGGERS = {                 # 什么算"特别"(要关哪类改 False)
    "first": True,           # 图鉴新种
    "record": True,          # 个人尺寸破纪录
    "legendary": True,       # 鱼王(Legendary竿感)
    "collect_high": True,    # 收藏品高分
}
COLLECT_HIGH_MULT = 2.0      # ★收藏品高分线 = 达标线×2 [待砍]
PAGE = 8                     # diary 一页显示条数
# ═════════════════════════════════════════════════════════

_REASON_CN = {"first": "图鉴新种", "record": "破纪录",
              "legendary": "鱼王", "collect_high": "收藏品高分"}


def maybe_record(state: dict, *, now: float, fish: dict, disp: str, size: float,
                 hq: bool, first: bool, rec: bool, prev_rec: float,
                 collect, bait_name, loc: str, zone: str, weather: str,
                 et: str, collect_min: int) -> int | None:
    """特别渔获 → 自动记一条"事实半"。返回条目编号, 不特别返回 None。"""
    reasons = []
    if TRIGGERS["first"] and first:
        reasons.append("first")
    if TRIGGERS["record"] and rec and prev_rec > 0:
        reasons.append("record")
    if TRIGGERS["legendary"] and fish.get("tug") == "Legendary":
        reasons.append("legendary")
    if (TRIGGERS["collect_high"] and collect and collect.get("ok")
            and collect["value"] >= collect_min * COLLECT_HIGH_MULT):
        reasons.append("collect_high")
    if not reasons:
        return None
    book = state.setdefault("diary", [])
    entry = {
        "id": (book[-1]["id"] + 1) if book else 1,
        "ts": now, "et": et, "weather": weather,
        "loc": loc, "zone": zone,
        "fish": fish["name"], "disp": disp,
        "size": size, "hq": hq,
        "bait": bait_name or "",
        "prev_rec": prev_rec if ("record" in reasons) else 0,
        "reasons": reasons,
        "moods": [],             # [{"ts":…, "text":…}] 只追加不覆盖
    }
    book.append(entry)
    return entry["id"]


# ── 展示 ─────────────────────────────────────────────────
def _head(e: dict) -> str:
    tags = "·".join(_REASON_CN[x] for x in e["reasons"])
    hq = " ✨HQ" if e["hq"] else ""
    place = e["loc"] if e["zone"] in ("", e["loc"]) else f"{e['loc']}（{e['zone']}）"
    return (f"📖 #{e['id']} · {e['et']} · {e['weather']} · {place}\n"
            f"   {e['disp']} {e['size']}吋{hq} —— {tags}"
            + (f"(旧纪录 {e['prev_rec']}吋)" if e.get("prev_rec") else "")
            + (f" · 饵: {e['bait']}" if e["bait"] else ""))


def _mood_lines(e: dict, full: bool) -> list:
    ms = e.get("moods", [])
    if not ms:
        return []
    show = ms if full else ms[-1:]
    out = []
    if not full and len(ms) > 1:
        out.append(f"   ♪ (…前面还有 {len(ms) - 1} 次心情, diary {e['id']} 全看)")
    for m in show:
        d = _dt.datetime.fromtimestamp(m["ts"]).strftime("%m-%d %H:%M")
        body = "\n     ".join(m["text"].split(" | "))
        out.append(f"   ♪ [{d}] {body}")
    return out


def render(state: dict, arg: str) -> str:
    """diary —— 翻手帐 / diary <编号> 单条全览 / diary <鱼名> 检索。"""
    book = state.get("diary", [])
    a = (arg or "").strip()
    if not book:
        return ("📖 钓鱼手帐还是空白的——钓到特别的鱼(图鉴新种/破纪录/鱼王/收藏品高分)\n"
                "   时会自动记下那一刻的天气、时间、钓场和尺寸。\n"
                "   心情由你自己补: diary mood <文字>（格式随意, 推荐一行情境+一行和弦）")
    if a.isdecimal():
        for e in book:
            if e["id"] == int(a):
                lines = [_head(e)] + _mood_lines(e, full=True)
                if not e.get("moods"):
                    lines.append("   ♪ (还没有记过心情——diary mood "
                                 f"{e['id']} <文字> 随时补, 可以反复追加)")
                return "\n".join(lines)
        return f"📖 手帐里没有 #{a} 这一条。"
    if a:
        hits = [e for e in book
                if a.lower() in e["fish"].lower() or a in e["disp"]]
        if not hits:
            return f"📖 手帐里翻不到「{a}」——它还没成为过\"特别的鱼\"。"
        out = [f"📖 「{a}」的手帐({len(hits)}条):"]
        for e in hits[-PAGE:]:
            out.append(_head(e))
            out += _mood_lines(e, full=False)
        return "\n".join(out)
    out = [f"📖 钓鱼手帐(共{len(book)}条, 最近{min(PAGE, len(book))}条; "
           "diary <编号>看单条 / diary <鱼名>检索 / diary mood 记心情)"]
    for e in book[-PAGE:][::-1]:
        out.append(_head(e))
        out += _mood_lines(e, full=False)
    return "\n".join(out)


def add_mood(state: dict, arg: str, now: float) -> str:
    """diary mood [编号] <文字> —— 给日记补心情。只追加, 永不覆盖。
    推荐(不强制)锚格式: 一行情境 | 一行和弦(≤4个, → 隔开, bpm可选)。"""
    book = state.get("diary", [])
    if not book:
        return "📖 手帐还是空白的, 先钓到一条特别的鱼吧。"
    parts = (arg or "").split(maxsplit=1)
    if parts and parts[0].isdecimal():
        eid = int(parts[0])
        text = parts[1] if len(parts) > 1 else ""
    else:
        eid = book[-1]["id"]
        text = (arg or "").strip()
    if not text:
        return ("📖 用法: diary mood [编号] <文字>\n"
                "   不带编号=记给最新一条。想分两行写, 用 | 隔开, 例:\n"
                "   diary mood 拉了三分钟才起竿, 尾鳍拍了我一脸水 | Fmaj9 → C/E · 72bpm")
    for e in book:
        if e["id"] == eid:
            e.setdefault("moods", []).append({"ts": now, "text": text})
            n = len(e["moods"])
            nth = "第一笔" if n == 1 else f"第{n}笔"
            return (f"📖 心情已记入 #{eid}「{e['disp']}」({nth})。\n"
                    f"   ——什么时候想再翻看, 随时可以再记一笔, 旧的不会被覆盖。")
    return f"📖 手帐里没有 #{eid} 这一条。"
