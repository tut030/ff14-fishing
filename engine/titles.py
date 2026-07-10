"""
FF14 钓鱼 大鱼称号系统
------------------------------------------------------------
钓到特定传说鱼 → 解锁称号 → 可佩戴展示

称号来源:
  1. 传说大鱼: 第一次钓到特定 Legendary 鱼时解锁
  2. 里程碑: 达成特定成就时解锁

命令:
  title      → 查看已解锁称号
  title <名> → 佩戴称号
  title off  → 摘下称号

★ 想加称号? 往 FISH_TITLES 或 MILESTONE_TITLES 追加即可 ★
"""

from __future__ import annotations

# 传说鱼称号: (鱼名(EN), 称号, 解锁语)
FISH_TITLES = [
    # ── 新手期 (Lv1-20) ──
    ("Octomammoth", "猛犸征服者",
     "你征服了利姆萨港的猛犸章鱼。小小的港口,大大的传说"),
    ("Chirurgeon", "手术刀与鱼钩",
     "外科医生落网——希望它没在你的鱼线上动手术"),
    ("Navigator's Brand", "航海之印",
     "连海神的印记都钓上来了,你是不是把海底翻了一遍?"),
    ("Junkmonger", "深海拾荒者",
     "拾荒鮟鱇上钩!它嘴里含着的垃圾比你鱼箱里的还多"),

    # ── 成长期 (Lv25-45) ──
    ("The Greatest Bream in the World", "大帝的对手",
     "你钓到了「世界上最伟大的鲷鱼」——名字比鱼大"),
    ("Old Hollow Eyes", "深渊的凝视",
     "虚空之眼在看着你。你也在看着它。谁先眨眼?"),
    ("Levinlight", "雷光追手",
     "抓住了闪电——不对,是闪电形状的鱼。但同样酷"),
    ("Shark Tuna", "鲨猎人",
     "金枪鲨!半鲨半鲔,比你的手臂粗。坐钩的回报来了"),
    ("Bloodbath", "浴血之手",
     "这条鱼名叫「血浴」——幸好只是名字"),

    # ── 中期 (Lv50-55) ──
    ("Nepto Dragon", "龙钓士",
     "涅普特龙——海中之龙。鱼竿弯成了弓,但你没有松手"),
    ("The Old Man in the Sea", "海的故人",
     "海中老人终于上岸了。你们对视了很久,谁也没说话"),
    ("Castaway Chocobo Chick", "陆行鸟救助者",
     "它不是鱼,是一只被冲走的陆行鸟幼崽……你把它救回来了"),
    ("Kuno the Killer", "暗杀者的天敌",
     "杀手库诺在你的线上挣扎——最终栽在了一根鱼竿手里"),

    # ── 高级 (Lv55-65) ──
    ("Flarefish", "核心钓手",
     "核爆鱼——名字听着像武器,其实只是发光而已。大概"),
    ("Dimorphodon", "翼龙猎手",
     "从天上钓翼龙?别人不信。但你有证据"),
    ("Aetherochemical Compound #666", "第666号实验体",
     "你从水里钓出了一份古代科技遗产。编号666。……不吉利?不,是传说"),

    # ── 后期 (Lv70) ──
    ("Diamond-eye", "钻石之瞳",
     "钻石眼。它用晶莹的目光看了你一眼——价值连城的那种"),
    ("Sculptor", "雕塑之友",
     "雕塑家鱼上钩了——据说每条的花纹都独一无二,像被雕刻过"),
    ("Stethacanthus", "远古之证",
     "胸脊鲨——三亿年前的化石活到了今天。比你的鱼竿年代久远得多"),
    ("Moksha", "解脱者",
     "解脱鱼。它上钩的瞬间,你好像听到了梵音……大概是耳鸣"),
]

# 里程碑称号: (达成条件检测函数, 称号, 解锁语)
MILESTONE_TITLES = [
    (lambda s: len(s.get("caught", {})) >= 100,
     "百鱼行者", "一百种鱼,一百段记忆"),
    (lambda s: len(s.get("caught", {})) >= 500,
     "图鉴贤者", "五百种鱼——连行会都得翻你的笔记"),
    (lambda s: s.get("level", 1) >= 100,
     "大钓师", "满级了。但你知道,这不是终点"),
    (lambda s: s.get("escapes", 0) >= 100,
     "不屈的竿", "脱钩一百次,抛竿一百零一次"),
    (lambda s: len(s.get("quests_done", [])) >= 20,
     "行会之光", "所有职业任务通关。会长可以退休了"),
]


def check_fish_title(state: dict, fish_name: str) -> tuple | None:
    """钓到鱼后检查是否解锁新称号。返回 (称号, 解锁语) 或 None。"""
    unlocked = set(state.get("titles", []))
    for fname, title, flavor in FISH_TITLES:
        if fname == fish_name and title not in unlocked:
            unlocked.add(title)
            state["titles"] = sorted(unlocked)
            return title, flavor
    return None


def check_milestones(state: dict) -> list:
    """检查里程碑称号。返回新解锁的 [(称号, 解锁语), ...]。"""
    unlocked = set(state.get("titles", []))
    news = []
    for check, title, flavor in MILESTONE_TITLES:
        if title not in unlocked and check(state):
            unlocked.add(title)
            news.append((title, flavor))
    if news:
        state["titles"] = sorted(unlocked)
    return news


def view(state: dict) -> str:
    """查看所有已解锁的称号。"""
    titles = state.get("titles", [])
    active = state.get("active_title")
    total = len(FISH_TITLES) + len(MILESTONE_TITLES)
    out = [f"🎖 称号 {len(titles)}/{total}"]
    if not titles:
        out.append("   还没有称号——钓到传说鱼就能解锁!")
        return "\n".join(out)
    for t in titles:
        mark = "◆" if t == active else " "
        out.append(f"   {mark} {t}")
    out.append(f"\n   title <名称> 佩戴 / title off 摘下"
               + (f"\n   当前佩戴: 「{active}」" if active else ""))
    return "\n".join(out)


def equip(state: dict, arg: str) -> str:
    """佩戴或摘下称号。"""
    if arg.lower() in ("off", "none", "取消", "摘下"):
        state["active_title"] = None
        return "称号已摘下。"
    titles = state.get("titles", [])
    if not titles:
        return "还没有称号——钓到传说鱼就能解锁!"
    # 模糊匹配
    matches = [t for t in titles if arg in t]
    if len(matches) == 1:
        state["active_title"] = matches[0]
        return f"称号已佩戴: 「{matches[0]}」"
    if len(matches) > 1:
        return "匹配到多个称号: " + "、".join(matches) + "——请输入更精确的名称。"
    return f"没有找到称号「{arg}」。title 查看已解锁的称号。"
