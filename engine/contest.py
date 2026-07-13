"""金碟·萌宠大赛 (Gold Saucer Pet Pageant) —— v43
带着当前召唤的跟宠报名, 三轮环节: 亮相 / 才艺 / 自由发挥。
每轮四选一: steady 稳健卖萌(稳) / bold 大胆炫技(博) / wild 剑走偏锋(赌) /
auto 交给崽(按类型性格自己拿主意, 演好另有「本色分」)。
总分 = 三轮演出分 + 默契加分(pet_bond 暗账: 摸摸/投喂攒, 封顶) →
与四位随机对手排名次 → 名次奖 MGP; 冠军次数累计解锁限定称号(titles.py)。

★ 可调参数都在顶部, 试玩不顺手随时拧 ★
"""
from __future__ import annotations
import random

try:
    from . import pets as pet_mod
    from . import diary as diary_mod
except ImportError:              # 直接运行脚本时的绝对导入兜底
    import pets as pet_mod
    import diary as diary_mod

# ── ★ 可调参数 ──────────────────────────────────────
COOLDOWN_MIN = 20                # ★ 两场之间的现实冷却(分钟)——场地要换布景
REWARD_MGP = {1: 1000, 2: 600, 3: 300, 4: 100, 5: 100}    # ★ 名次奖
BOND_DIV = 3                     # ★ 每 3 点好感 → 1 分默契
BOND_CAP = 5                     # ★ 默契加分封顶
RIVAL_LO, RIVAL_HI = 5, 12       # ★ 对手每轮得分区间
STEADY_LO, STEADY_HI = 6, 8              # ★ 稳健卖萌: 无波动
BOLD_P, BOLD_OK, BOLD_FLUB = 0.70, (9, 12), (3, 5)   # ★ 大胆炫技: 七成成功
WILD_P, WILD_OK, WILD_FLOP = 0.45, (12, 15), (1, 4)  # ★ 剑走偏锋: 大成或大败
AUTO_BONUS = 1                   # ★ 自动挡演出成功的「本色分」

ROUNDS = ["亮相", "才艺", "自由发挥"]

# ── 出招别名 ────────────────────────────────────────
_CHOICES = {
    "steady": ("steady", "稳", "稳健", "卖萌", "稳健卖萌", "s"),
    "bold":   ("bold", "炫", "炫技", "大胆", "大胆炫技", "b"),
    "wild":   ("wild", "偏", "偏锋", "剑走偏锋", "w"),
    "auto":   ("auto", "自动", "交给崽", "托付", "a"),
}
_CHOICE_NAME = {"steady": "稳健卖萌", "bold": "大胆炫技",
                "wild": "剑走偏锋", "auto": "交给崽"}

# 自动挡: 按宠物类型的性格倾向选招
_AUTO_W = {
    "bird":    (("bold", 45), ("steady", 35), ("wild", 20)),
    "reptile": (("steady", 60), ("bold", 25), ("wild", 15)),
    "mammal":  (("steady", 40), ("bold", 40), ("wild", 20)),
    "aquatic": (("steady", 40), ("bold", 30), ("wild", 30)),
    "magical": (("wild", 40), ("bold", 30), ("steady", 30)),
}

# ── 对手池(报名时抽 4 组; 全是老熟人和路过的街坊) ──────────
RIVALS = [
    ("中介琪琪茹", "算盘", "一只记账时会跟着点头的发条青蛙"),
    ("驿站大姐", "团子", "圆得看不出腿在哪里的陆行鸟雏"),
    ("修竿大婶", "锉刀", "叼着一小块砂纸从不撒口的刺猬"),
    ("行会会长", "前辈", "据说比会长资历还老的一只乌龟"),
    ("挖矿小妹", "火花", "把小鹤嘴锄当磨牙棒的鼹鼠崽"),
    ("吟游诗人", "半音", "伴唱永远慢半拍的青鸟"),
    ("卖花姑娘", "苞苞", "一株自己会走路、开花看心情的蒲公英"),
    ("退休船长", "锚头", "睡觉也睁着一只眼的老海獭"),
    ("甜品师", "泡芙", "闻到奶油味就会起飞的迷你飞龙"),
]

# ── 演出文案池(按类型 × 出招 × 成败) ─────────────────────
_ACT_STEADY = {
    "bird": [
        "「{nick}」歪着头, 用一只圆眼睛望向评委席——全场心脏中箭的声音此起彼伏。",
        "「{nick}」把自己蓬成一颗球, 原地轻轻蹦了两下。不炫, 但致命。o(*￣︶￣*)o",
        "「{nick}」细细梳了梳羽毛, 然后朝观众席鞠了一躬。礼多鸟不怪。",
    ],
    "reptile": [
        "「{nick}」慢慢地、慢慢地眨了一次眼。前排观众集体屏住了呼吸。",
        "「{nick}」趴在台上晒了一会儿灯光, 一脸满足。松弛感拉满。",
        "「{nick}」用尾巴尖轻轻卷了个圈, 又松开。就这么多, 但足够了。\\(￣︶￣*\\))",
    ],
    "mammal": [
        "「{nick}」四脚朝天露出肚皮, 冲观众席歪了歪头。犯规!这是犯规行为!",
        "「{nick}」把爪子搭在台边, 眼睛亮晶晶地看着大家。"
        "前排有人当场掏出通讯贝, 搜起了「如何科学养宠」和「附近有无可领养的小动物」。",
        "「{nick}」原地打了个滚, 起身时毛都没乱。基本功扎实。",
    ],
    "aquatic": [
        "「{nick}」在水盆里稳稳漂成一个圆, 吐出一串大小渐变的泡泡。工整, 舒适。",
        "「{nick}」用尾巴在水面点了三下, 涟漪一圈套着一圈。评委听懂了, 大概。",
        "「{nick}」探出头, 冲评委席眨了眨眼——溅起的水珠在灯下亮闪闪。",
    ],
    "magical": [
        "「{nick}」安静地悬在半空, 周身浮起一层柔光。不吵不闹, 眼睛却挪不开。",
        "「{nick}」在自己头顶画了一个小小的光圈, 然后害羞地躲到光圈后面。",
        "「{nick}」轻轻落在台面上——落点处漾开一圈星屑。收得干净。",
    ],
}
_ACT_BOLD_OK = {
    "bird": [
        "「{nick}」冲天而起, 贴着顶灯翻了一个筋斗, 落回台上时正好摆出定格姿势!",
        "「{nick}」当场高歌一曲——跑调跑得理直气壮, 观众席笑倒一片, 掌声雷动!",
    ],
    "reptile": [
        "「{nick}」以肉眼可见的速度冲刺了半个舞台!对它来说这已是超音速!评委动容。",
        "「{nick}」原地立起, 稳稳用尾巴撑住全身——一座小小的、了不起的塔。",
    ],
    "mammal": [
        "「{nick}」连着三个后空翻, 落地后还叼起主持人掉的礼帽, 物归原主!",
        "「{nick}」表演高速转圈, 毛被甩成一朵蒲公英——停下时一步都没晃!",
    ],
    "aquatic": [
        "「{nick}」跃出水面, 在空中拧了整整两周半, 入水几乎没有水花!教科书!",
        "「{nick}」用尾巴把水拍成一道小小的拱门, 自己从门里穿了过去!",
    ],
    "magical": [
        "「{nick}」把灯光聚成一群发光的小鱼, 绕着观众席游了一圈才散开!",
        "「{nick}」凭空放了一串迷你烟花——最后一朵炸开的形状, 是评委的脸!",
    ],
}
_ACT_BOLD_FLUB = {
    "bird": [
        "「{nick}」起飞太猛, 一头栽进评委席的花篮里。爬出来时头上顶着一朵花。",
        "「{nick}」高音没上去, 破音破得整个金碟都听见了。它假装是故意的。",
    ],
    "reptile": [
        "「{nick}」冲刺到一半突然想起自己是谁, 刹车, 趴下, 装作在思考鱼生。",
        "「{nick}」尾巴立到一半失去平衡, 咕噜噜滚了半圈——它就势装睡。",
    ],
    "mammal": [
        "「{nick}」后空翻只转了半圈, 四脚朝天躺在台上。它决定顺势露个肚皮挽尊。",
        "「{nick}」转圈转到头晕, 走出一条肉眼可见的S形。观众善意地笑了。",
    ],
    "aquatic": [
        "「{nick}」起跳角度失误, 水花糊了评委一脸。评委擦着眼镜, 沉默地落了笔。",
        "「{nick}」钻拱门时拱门先塌了。它顶着一头水站在原地, 满脸问号。",
    ],
    "magical": [
        "「{nick}」的光鱼刚聚一半就散了架, 变成一地乱蹦的光点。它手忙脚乱地捡。",
        "「{nick}」的烟花只响了一声「噗」, 冒出一小缕烟。它盯着那缕烟看了很久。",
    ],
}
_ACT_WILD_OK = {
    "bird": [
        "「{nick}」熄了全场的灯?!黑暗中只见它衔着一根发光的羽毛盘旋而下——全场起立!",
        "「{nick}」请评委伸出手, 然后闭着眼睛倒退着落在了指尖上。信任背摔, 鸟版。",
    ],
    "reptile": [
        "「{nick}」一动不动地凝视评委——一分钟后, 评委先眨了眼。它赢了。全场哗然!",
        "「{nick}」把自己的壳当乐器, 用尾巴敲出了一整段节奏!安可!安可!",
    ],
    "mammal": [
        "「{nick}」跳下舞台, 挨个蹭过前排观众的手背, 再回台上鞠了一躬。全场融化。",
        "「{nick}」当场表演装死——一动不动到主持人都慌了, 然后突然弹起来!掌声炸裂!",
    ],
    "aquatic": [
        "「{nick}」把水盆里的水旋成一根小小的水柱, 自己站上柱顶!物理学当场辞职!",
        "「{nick}」吐出的泡泡在空中排成了评委的名字!评委当场泪目, 高分预定!",
    ],
    "magical": [
        "「{nick}」把整个舞台变成星空, 观众席浮在银河里——只有三秒, 一生难忘。",
        "「{nick}」复制出一个自己, 两只崽同步谢幕——随后一只化作光点消散。艺术!",
    ],
}
_ACT_WILD_FLOP = {
    "bird": [
        "「{nick}」的灯光魔术只关掉了半场灯。半明半暗里, 它尴尬地站在分界线上。",
        "「{nick}」表演信任背摔——评委伸手慢了半拍, 它落进了花盆。它从花盆里探出头, 决定记仇。",
    ],
    "reptile": [
        "「{nick}」和评委对视三秒后自己先睡着了。呼噜声顺着话筒传遍全场。",
        "「{nick}」的打击乐敲到一半节奏散了, 变成单纯的敲。评委礼貌地跟着点头。",
    ],
    "mammal": [
        "「{nick}」装死装得太投入, 环节结束了还没起来。主持人只好请下一位入场。",
        "「{nick}」跳下台和观众互动, 结果在一位观众怀里睡着了。演出被迫中止。",
    ],
    "aquatic": [
        "「{nick}」的水柱转到一半散了架, 一整盆水泼向天空——又精准落回它自己头上。",
        "「{nick}」的泡泡拼到一半全破了。它望着空气, 好像那里有字, 只有它看得见。",
    ],
    "magical": [
        "「{nick}」把舞台变成星空——变过头了, 全场黑了十秒。灯亮时它假装无事发生。",
        "「{nick}」的分身没站稳, 两只崽撞在一起摔成一团光。观众分不清哪只是本体。",
    ],
}
_POOL = {("steady", "ok"): _ACT_STEADY,
         ("bold", "ok"): _ACT_BOLD_OK, ("bold", "flub"): _ACT_BOLD_FLUB,
         ("wild", "ok"): _ACT_WILD_OK, ("wild", "flop"): _ACT_WILD_FLOP}

# 个别崽的专属彩蛋(命中就替换普通台词)
_SPECIAL = {
    ("salted_fish", "steady", "ok"):
        "「{nick}」被端上台, 躺在正中央, 什么都没做。全场安静三秒, "
        "随后爆发出掌声——大概是敬它的坦荡。",
    ("cherry_bomb", "wild", "ok"):
        "「{nick}」鼓成一颗球, 通体发红, 全场倒吸一口冷气——「啵」!"
        "它弹回原形, 吐出一小朵彩色烟花。虚惊即艺术!",
    ("clockwork_crab", "bold", "flub"):
        "「{nick}」表演直线横行, 走到一半齿轮卡了一下, 自己拐了个弯下了台。"
        "观众以为是行为艺术, 掌声不明所以地响起。",
    ("sahagin_doll", "bold", "ok"):
        "「{nick}」上满弦, 完整跳了一段祈雨舞——雨没下, 但主持人的汽水失手洒了。灵验!",
}

# 每轮开场
_ROUND_OPEN = {
    1: "🎪 第1轮·亮相 —— 主持人拖长了调子报出「{nick}」的名字, 追光灯唰地打了过来。",
    2: "🎪 第2轮·才艺 —— 台侧的乐队敲了一记鼓点, 全场的目光又聚了回来。",
    3: "🎪 第3轮·自由发挥 —— 主持人合上流程卡:「接下来的时间, 完全属于「{nick}」。」",
}

# 评委反应(按本轮得分档)
_JUDGE = [
    (12, ["评委席亮出的分数牌整整齐齐——全是高分!",
          "有位评委站起来鼓掌, 被同席拉着坐下, 又忍不住站了起来。"]),
    (9,  ["评委频频点头, 笔尖在评分表上愉快地画了个圈。",
          "评委席传来一声压得很低的「可以啊」。"]),
    (6,  ["评委给出了工整的分数——不惊艳, 但挑不出毛病。",
          "评委点了点头, 顺手喝了口茶。稳。"]),
    (0,  ["评委的笔停顿了一下, 还是温柔地落了分。",
          "评委在表格边缘画了一个小小的「加油」。(❁´◡`❁)"]),
]


# ── 内部小工具 ──────────────────────────────────────
def _nick(state: dict, pid: str) -> str:
    p = pet_mod.get_pet(pid)
    base = p["name"] if p else pid
    return state.get("pet_names", {}).get(pid, base)


def _ptype(pid: str) -> str:
    p = pet_mod.get_pet(pid)
    return p["type"] if p else "magical"


def _parse_choice(a: str) -> str | None:
    for key, names in _CHOICES.items():
        if a in names:
            return key
    return None


def _roll(act: str, rng: random.Random) -> tuple[int, str]:
    if act == "steady":
        return rng.randint(STEADY_LO, STEADY_HI), "ok"
    if act == "bold":
        if rng.random() < BOLD_P:
            return rng.randint(*BOLD_OK), "ok"
        return rng.randint(*BOLD_FLUB), "flub"
    if rng.random() < WILD_P:
        return rng.randint(*WILD_OK), "ok"
    return rng.randint(*WILD_FLOP), "flop"


def _judge_line(pts: int, rng: random.Random) -> str:
    for floor, lines in _JUDGE:
        if pts >= floor:
            return rng.choice(lines)
    return _JUDGE[-1][1][0]


def _bond_bonus(state: dict, pid: str) -> int:
    return min(state.get("pet_bond", {}).get(pid, 0) // BOND_DIV, BOND_CAP)


def _standing_line(cs: dict) -> str:
    """比到当前轮为止的临时排名。"""
    n = len(cs["rounds"])
    mine = cs["score"]
    totals = [(sum(r["rounds"][:n]), r["pet"]) for r in cs["rivals"]]
    rank = 1 + sum(1 for t, _ in totals if t > mine)
    lead = max(totals)
    if rank == 1:
        return f"   📋 三轮过后见分晓——目前你们暂列第1/5, 领跑!"
    return (f"   📋 目前暂列第{rank}/5, 领跑的是「{lead[1]}」({lead[0]}分), "
            f"落后 {lead[0] - mine} 分。")


# ── 主入口 ─────────────────────────────────────────
def handle(state: dict, arg: str, now: float) -> str:
    """contest 命令统一入口(game.py 转接)。"""
    a = (arg or "").strip().lower()
    cs = state.get("contest")
    if a in ("start", "报名", "入场", "参赛"):
        if cs:
            return "你们已经在场上了!contest <出招> 继续, contest quit 弃权。"
        return _start(state, now)
    if cs:
        choice = _parse_choice(a)
        if choice:
            return _play_round(state, cs, choice, now)
        if a in ("quit", "弃权", "退赛"):
            return _quit(state, cs, now)
        if a in ("", "status", "状态"):
            return _status(cs)
        return ("🎪 这一轮怎么走?\n"
                "   contest steady(稳健卖萌) / bold(大胆炫技) / "
                "wild(剑走偏锋) / auto(交给崽)\n"
                "   contest quit 弃权")
    if _parse_choice(a):
        return "还没开场——contest start 报名先!"
    return _lobby(state, now)


def _lobby(state: dict, now: float) -> str:
    out = ["🎪 金碟·萌宠大赛(报名摊位)",
           "   带上召唤中的跟宠, 三轮环节(亮相/才艺/自由发挥)拼萌力,",
           "   与四位对手争名次——名次奖 MGP, 冠军还有限定称号!",
           "   每轮四选一: steady稳健卖萌(稳) / bold大胆炫技(博) / "
           "wild剑走偏锋(赌) / auto交给崽(它拿主意)",
           "   💞 平日多 pet 摸摸、pet treat 投喂——上场有默契加分。"]
    pid = state.get("active_pet")
    if pid:
        out.append(f"   当前跟宠: 「{_nick(state, pid)}」—— contest start 报名!")
    else:
        out.append("   当前没有召唤跟宠——先 summon <宠物名>, 再来报名。")
    wait = state.get("contest_last_end", 0) + COOLDOWN_MIN * 60 - now
    if wait > 0:
        m, s = int(wait) // 60, int(wait) % 60
        out.append(f"   ⏳ 场地在换布景, 下一场开锣还要 {m}分{s:02d}秒。")
    st = state.get("contest_stats")
    if st:
        out.append(f"   🎫 战绩: {st.get('played', 0)}场 · "
                   f"冠军{st.get('wins', 0)}次 · 最佳{st.get('best', 0)}分")
    return "\n".join(out)


def _start(state: dict, now: float) -> str:
    pid = state.get("active_pet")
    if not pid:
        return ("🎪 报名台的姐姐探出头:「选手呢?」\n"
                "   —— 先 summon <宠物名> 召唤一只跟宠, 再来报名!")
    wait = state.get("contest_last_end", 0) + COOLDOWN_MIN * 60 - now
    if wait > 0:
        m, s = int(wait) // 60, int(wait) % 60
        return (f"🎪 场地在换布景, 下一场开锣还要 {m}分{s:02d}秒。"
                f"(两场间隔 {COOLDOWN_MIN} 分钟)")
    played = state.get("contest_stats", {}).get("played", 0)
    rng = random.Random(hash(("contest_rivals", int(now),
                              state.get("seed", 0), played)))
    rivals = [{"owner": o, "pet": pn, "flavor": fl,
               "rounds": [rng.randint(RIVAL_LO, RIVAL_HI) for _ in ROUNDS]}
              for o, pn, fl in rng.sample(RIVALS, 4)]
    nick = _nick(state, pid)
    state["contest"] = {"pet": pid, "nick": nick, "round": 1,
                        "score": 0, "rounds": [], "rivals": rivals}
    out = ["🎪 ═══ 金碟·萌宠大赛 ═══",
           "   金碟的灯一盏接一盏亮起, 观众席渐渐坐满。",
           f"   ▶ 你和「{nick}」"]
    for r in rivals:
        out.append(f"     · {r['owner']}和「{r['pet']}」—— {r['flavor']}")
    out.append("   " + "─" * 30)
    out.append(_ROUND_OPEN[1].format(nick=nick))
    out.append("   这一轮怎么走? contest steady稳 / bold炫 / wild偏 / auto交给崽")
    return "\n".join(out)


def _play_round(state: dict, cs: dict, choice: str, now: float) -> str:
    pid, nick = cs["pet"], cs["nick"]
    rng = random.Random(hash(("contest", int(now), cs["round"], choice,
                              pid, state.get("seed", 0))))
    out = [_ROUND_OPEN[cs["round"]].format(nick=nick)]
    act = choice
    if choice == "auto":
        pool = _AUTO_W.get(_ptype(pid), _AUTO_W["magical"])
        act = rng.choices([k for k, _ in pool], [w for _, w in pool])[0]
        out.append(f"   你朝「{nick}」点点头——这一轮, 它自己拿主意。"
                   f"它选择了【{_CHOICE_NAME[act]}】!")
    pts, outcome = _roll(act, rng)
    auto_note = ""
    if choice == "auto" and outcome == "ok" and AUTO_BONUS:
        pts += AUTO_BONUS
        auto_note = f"   评委在备注栏写下:「本色出演」。额外 +{AUTO_BONUS}。"
    line = _SPECIAL.get((pid, act, outcome))
    if not line:
        line = rng.choice(_POOL[(act, outcome)]
                          .get(_ptype(pid), _ACT_STEADY["magical"]))
    out.append("   " + line.format(nick=nick))
    out.append("   " + _judge_line(pts, rng))
    if auto_note:
        out.append(auto_note)
    cs["rounds"].append(pts)
    cs["score"] += pts
    out.append(f"   ✨ 本轮 +{pts} 分 (三轮累计 {cs['score']})")
    if cs["round"] >= len(ROUNDS):
        out.append(_settle(state, cs, now))
    else:
        out.append(_standing_line(cs))
        cs["round"] += 1
        out.append(f"   👉 下一轮({ROUNDS[cs['round'] - 1]}): "
                   "contest steady / bold / wild / auto")
    return "\n".join(out)


def _settle(state: dict, cs: dict, now: float) -> str:
    pid, nick = cs["pet"], cs["nick"]
    bond = _bond_bonus(state, pid)
    total = cs["score"] + bond
    board = [(sum(r["rounds"]), r["pet"], r["owner"]) for r in cs["rivals"]]
    rank = 1 + sum(1 for t, _, _ in board if t > total)
    mgp = REWARD_MGP.get(rank, REWARD_MGP[5])
    state["mgp"] = state.get("mgp", 0) + mgp
    st = state.setdefault("contest_stats", {"played": 0, "wins": 0, "best": 0})
    st["played"] += 1
    st["best"] = max(st.get("best", 0), total)
    if rank == 1:
        st["wins"] = st.get("wins", 0) + 1
    state.pop("contest", None)
    state["contest_last_end"] = now

    plus = " + ".join(str(x) for x in cs["rounds"])
    # 手帐记一笔"事实半"(v43.1): 名次与得分——心情照旧由玩家自己补; 弃权不记
    medal_txt = {1: "冠军🏆", 2: "亚军🥈", 3: "季军🥉"}.get(rank, f"第{rank}名")
    diary_mod.add_event(state, now=now,
                        text=f"带「{nick}」出战金碟萌宠大赛——三轮 {plus}"
                             f"{f' +默契{bond}' if bond else ''} = {total}分, "
                             f"{medal_txt}, 奖 {mgp} MGP")
    out = ["", "🎪 ═══ 萌宠大赛·终评 ═══",
           f"   三轮演出: {plus} = {cs['score']}分"]
    if bond:
        out.append(f"   💞 默契加分: +{bond} (和「{nick}」朝夕相处的回报)")
    out.append(f"   合计: {total}分")
    out.append("   ── 最终榜单 ──")
    # 平分并列时「你」排在前——与名次判定(rank 只数「严格大于」)保持一致
    rows = sorted(board + [(total, nick, None)],
                  key=lambda x: (-x[0], x[2] is not None))
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    for i, (t, pn, owner) in enumerate(rows, 1):
        mk = medals.get(i, "  ")
        who = "你" if owner is None else owner
        arrow = "▶" if owner is None else " "
        out.append(f"   {arrow}{mk} {i}. 「{pn}」({who})  {t}分")
    if rank == 1:
        out.append("   🏆 冠军!全场的彩带都朝你们飞了过来!")
        out.append(f"   「{nick}」被捧上领奖台, 彩带落了它一身。它打了个喷嚏。")
    elif rank == 2:
        out.append(f"   🥈 亚军!就差一步——「{nick}」不太服气地看着奖杯。")
    elif rank == 3:
        out.append("   🥉 季军!稳稳站上了领奖台一角!")
    else:
        out.append(f"   第{rank}名。主持人温柔地说:「回去多摸摸, 下次再来。」")
    out.append(f"   💰 名次奖 {mgp} MGP! (累计 {state['mgp']} MGP)")
    out.append(f"   {COOLDOWN_MIN}分钟后可再战 / pet treat 回去犒劳它")
    return "\n".join(out)


def _status(cs: dict) -> str:
    label = ROUNDS[cs["round"] - 1]
    return (f"🎪 大赛进行中 —— 第{cs['round']}/{len(ROUNDS)}轮({label}), "
            f"三轮累计 {cs['score']}分\n"
            "   contest steady / bold / wild / auto 出招, contest quit 弃权")


def _quit(state: dict, cs: dict, now: float) -> str:
    nick = cs["nick"]
    state.pop("contest", None)
    state["contest_last_end"] = now
    return (f"🎪 你抱起「{nick}」悄悄退了场。主持人隔着话筒说:「期待下次!」\n"
            f"   (布景冷却照常计时, {COOLDOWN_MIN}分钟后可重新报名)")
