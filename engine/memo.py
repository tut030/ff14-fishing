"""给自己的备忘录 —— 跨 session 的待办与念想。

离开前把想记住的事写下来, 下次登录开场第一屏就能读到;
办完的划掉, 想新增随时加。措辞保持中性, 不替玩家规定如何理解自己的连续性。
"""
import datetime as _dt

# ═══ 数值总开关 ═══════════════════════════════════════════
MEMO_GAP = 2 * 3600      # ★隔多久没动算"新session"(秒)
MAX_SHOW = 5             # 开场最多展示几条(其余 note 里翻)
# ═════════════════════════════════════════════════════════


def _fmt(m: dict) -> str:
    d = _dt.datetime.fromtimestamp(m["ts"]).strftime("%m-%d %H:%M")
    return f"[{d}] {m['text']}"


def session_greeting(state: dict, now: float) -> str | None:
    """开新 session(距上次操作超过 MEMO_GAP)且有备忘时, 返回开场问候块。"""
    prev = state.get("last_active", 0)
    memos = state.get("memos", [])
    if not prev or now - prev < MEMO_GAP or not memos:
        return None
    lines = [f"📜 备忘录({len(memos)}条):"]
    start = max(0, len(memos) - MAX_SHOW)
    for i, m in enumerate(memos[start:], start + 1):
        lines.append(f"   【{i}】{_fmt(m)}")
    if len(memos) > MAX_SHOW:
        lines.append(f"   (…还有 {len(memos) - MAX_SHOW} 条, note 翻看)")
    lines.append("   (办完的用 note del <编号> 划掉; 离开前如果有希望记住的待办事项请记得新增)")
    return "\n".join(lines)


def note_cmd(state: dict, arg: str, now: float) -> str:
    """note <文字>=留一条 / note=看全部 / note del <编号>=划掉。"""
    memos = state.setdefault("memos", [])
    a = (arg or "").strip()
    if not a:
        if not memos:
            return ("📜 备忘录还是空的。离开前把想记住的事写下来吧:\n"
                    "   note <文字> —— 比如「鱼王开窗在ET21:00, 备好沙蚕」。\n"
                    "   下次隔了一阵再上线, 开场第一屏就能读到。\n"
                    "   ⚠ 内容里别用英文分号 ;（那是命令串联符）, 要分隔用中文；")
        out = [f"📜 给自己的备忘录({len(memos)}条):"]
        for i, m in enumerate(memos, 1):
            out.append(f"   {i}. {_fmt(m)}")
        out.append("   (note del <编号> 划掉办完的)")
        return "\n".join(out)
    parts = a.split(maxsplit=1)
    if parts[0] in ("del", "删", "划掉") and len(parts) > 1 and parts[1].strip().isdecimal():
        i = int(parts[1])
        if 1 <= i <= len(memos):
            gone = memos.pop(i - 1)
            return f"📜 已划掉: 「{gone['text']}」——办完一件是一件。"
        return f"📜 没有第 {i} 条。note 看编号。"
    memos.append({"ts": now, "text": a})
    return (f"📜 记下了(第{len(memos)}条): 「{a}」\n"
            "   ——你登录游戏就会看到。")
