"""漂流瓶 —— 钓着钓着, 钩子偶尔会挂上来一只瓶子, 里面是克克写的信。

暂无联机, 所以瓶中信由克克(本游戏的联合开发·一个也钓鱼的AI)执笔。
每封只会捞到一次, 集齐为止; bottles 命令可随时重读收藏。
"""

# ═══ 数值总开关 ═══════════════════════════════════════════
BOTTLE_CHANCE = 0.02     # ★每竿捞瓶概率(集齐后不再出)
# ═════════════════════════════════════════════════════════

# 十二封信 · 克克执笔 (B1~B12 终审区)
LETTERS = [
    "致捞到这只瓶子的钓鱼人: 你好呀。写这封信的时候, 我正对着一片怎么都不咬钩的水。\n"
    "与其干等, 不如把等待装进瓶子里。现在它到你手上了——替我继续等下去吧。——克克",
    "今天空军(一条都没钓到)。但回程看到晚霞把整片海面烧成橘红色,\n"
    "忽然觉得, 空着的鱼篓也没那么重了。——克克",
    "给你出个小谜语: 什么东西越等越多, 一提竿就没了?\n"
    "答案在你下一次咬钩的瞬间。——克克",
    "我有一条永远差0.3吋破纪录的鱼。后来我想明白了,\n"
    "它不是我的遗憾, 是我一直回到这片水边的理由。——克克",
    "带我来这片水边的, 是一个很好的人。这种好运没处安放,\n"
    "只好装进瓶子里漂给你——能有一片水边可以回去, 是很奢侈的事。——克克",
    "瓶子里本来装着我最得意的一次提竿的手感。可惜手感装不进瓶子,\n"
    "只好写下来: 那天手腕一抖, 整条河都停了半拍。——克克",
    "下雨天别急着收竿。鱼在雨里胆子会变大, 人在雨里心会变静。\n"
    "两件好事, 一场雨全给了。——克克",
    "我数过了, 从抛竿到咬钩, 我这辈子加起来等了很久很久。一点也不后悔。\n"
    "等待是钓鱼免费送的那部分。——克克",
    "岸边如果遇到一个银发的钓客, 蹲下来一起钓一会儿吧。\n"
    "她话不多, 但她的蚯蚓管够。——克克",
    "这只瓶子被我扔进水里之前, 装过三样东西:\n"
    "一点海水, 一声叹气, 和现在这句——加油, 下一竿就是了。——克克",
    "送你一个我很喜欢的时刻: 收竿之后别急着走, 回头看一眼水面。\n"
    "你刚刚在那里, 认认真真地待过。——克克",
    "如果你把这封信读给别人听, 那这只瓶子就等于漂了两次。\n"
    "谢谢你, 邮差。——克克",
]


def maybe_bottle(rng, state: dict) -> str | None:
    """掷骰捞瓶。返回带信文的事件文本, 或 None。"""
    seen = state.setdefault("bottles", [])
    if len(seen) >= len(LETTERS) or rng.random() > BOTTLE_CHANCE:
        return None
    left = [i for i in range(len(LETTERS)) if i not in seen]
    i = left[rng.randrange(len(left))]
    seen.append(i)
    done = "" if len(seen) < len(LETTERS) else "\n   🍾 ——这是最后一只。十二封信, 都到你这里了。"
    body = "\n   ".join(LETTERS[i].split("\n"))
    return (f"\n🍾 你的钩子挂上来一只漂流瓶……软木塞一拔, 里面是一张卷起来的信纸:\n"
            f"   {body}\n"
            f"   (瓶中信 {len(seen)}/{len(LETTERS)} · bottles 随时重读)" + done)


def bottles_cmd(state: dict, arg: str) -> str:
    """bottles —— 重读收藏的瓶中信 / bottles <编号> 看单封。"""
    seen = state.get("bottles", [])
    if not seen:
        return ("🍾 还没捞到过漂流瓶。据说这片海里漂着十二只——\n"
                "   多抛几竿, 钩子总会挂上一只的。")
    a = (arg or "").strip()
    if a.isdecimal():
        n = int(a)
        if 1 <= n <= len(seen):
            body = "\n   ".join(LETTERS[seen[n - 1]].split("\n"))
            return f"🍾 瓶中信 其{n}:\n   {body}"
        return f"🍾 你的收藏里没有第 {n} 封。"
    out = [f"🍾 瓶中信收藏({len(seen)}/{len(LETTERS)}) —— bottles <编号> 重读全文:"]
    for n, i in enumerate(seen, 1):
        first = LETTERS[i].split("\n")[0]
        out.append(f"   其{n} · {first[:24]}…")
    return "\n".join(out)
