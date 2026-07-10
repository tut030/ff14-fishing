"""宠物 & 坐骑系统。
获得途径: 钓特定鱼 / 成就里程碑 / MGP 兑换。
纯情绪价值——无数值效果, 但会自己冒出来和你互动。
"""
import random

# ── 宠物定义 ────────────────────────────────────────
# type: bird / reptile / mammal / aquatic / magical
# source: fish=钓特定鱼 / ach=成就里程碑 / mgp=金碟兑换
PETS = [
    # ── 钓鱼获得 ──
    {"id": "chocobo_chick", "name": "巧儿海陆行鸟", "en": "Castaway Chocobo Chick",
     "type": "bird", "source": "fish", "fish": "Castaway Chocobo Chick",
     "desc": "能横渡大海的陆行鸟之子。虽然不会游泳，但会在你肩上打盹。"},
    {"id": "tiny_tortoise", "name": "小海龟", "en": "Tiny Tortoise",
     "type": "reptile", "source": "fish", "fish": "Gigant Clam",
     "desc": "从巨蛤里救出来的小海龟。走得很慢，但一直跟着你。"},
    {"id": "magic_bucket_fish", "name": "桶中鱼精", "en": "Bucket Fish Spirit",
     "type": "aquatic", "source": "fish", "fish": "Cupfish",
     "desc": "鱼大叔。你把它养在了一个小木桶里。它偶尔会从桶里探头看你。"},
    {"id": "star_crab", "name": "星光蟹", "en": "Star Crab",
     "type": "aquatic", "source": "fish", "fish": "Pebble Crab",
     "desc": "壳上有星星图案的小螃蟹。晚上会微微发光。"},
    # ── 成就里程碑 ──
    {"id": "fisher_sprite", "name": "小鱼精灵", "en": "Fisher Sprite",
     "type": "magical", "source": "ach", "req_caught": 50,
     "desc": "据说是海中精灵送给努力钓鱼的人的礼物。浑身透明，在阳光下泛着彩虹色。"},
    {"id": "otter_pup", "name": "钓鱼獭崽", "en": "Otter Pup",
     "type": "mammal", "source": "ach", "req_caught": 150,
     "desc": "一只小水獭。它比你更会钓鱼——但它选择跟你混。"},
    {"id": "baby_whale", "name": "迷你座头鲸", "en": "Mini Humpback",
     "type": "aquatic", "source": "ach", "req_caught": 300,
     "desc": "一头住在鱼缸里的缩小版座头鲸。不知道为什么，它能唱歌。"},
    {"id": "phoenix_chick", "name": "火鸟雏", "en": "Phoenix Chick",
     "type": "bird", "source": "ach", "req_caught": 500,
     "desc": "传说中从火焰中诞生的雏鸟。翅膀末端有微弱的火光。它怕水。"},
    {"id": "dragon_pup", "name": "霜龙幼崽", "en": "Frost Whelpling",
     "type": "reptile", "source": "ach", "req_ocean": 100,
     "desc": "在海钓途中捡到的蛋里孵出来的。吐出来的是冰，不是火。"},
    # ── MGP 兑换 ──
    {"id": "golden_chocobo", "name": "金碟迷你陆行鸟", "en": "Golden Mini Chocobo",
     "type": "bird", "source": "mgp", "mgp_cost": 500,
     "desc": "金光闪闪的小陆行鸟。是金碟游乐场的吉祥物。走路的时候会撒金粉。"},
    {"id": "clockwork_crab", "name": "发条螃蟹", "en": "Clockwork Crab",
     "type": "mammal", "source": "mgp", "mgp_cost": 1200,
     "desc": "用齿轮和弹簧做成的机械螃蟹。偶尔会自己拐弯。"},
]

# ── 坐骑定义 ────────────────────────────────────────
MOUNTS = [
    {"id": "fishing_boat", "name": "钓鱼小船", "en": "Fishing Dinghy",
     "type": "boat", "source": "ach", "req_caught": 100,
     "desc": "一条不大的小船。桨有点旧，底漆有点剥——充满了生活气息。"},
    {"id": "fat_chocobo", "name": "胖陆行鸟", "en": "Fat Chocobo",
     "type": "chocobo", "source": "ach", "req_caught": 200,
     "desc": "一只吃太多的陆行鸟。哦不，不胖，好的，虚胖。都是羽毛太蓬松。我错了别咬我！咳咳。走得很快，坐着也很舒服。"},
    {"id": "turtle_mount", "name": "巨龟", "en": "Giant Tortoise",
     "type": "reptile", "source": "ach", "req_caught": 400,
     "desc": "背上可以坐人的巨型海龟。飞起来的时候可以边自转边前进。"},
    {"id": "sea_horse", "name": "海马骑兵", "en": "Sea Horse",
     "type": "aquatic", "source": "ach", "req_ocean": 150,
     "desc": "正经的海马——可以骑的那种。在有水的地方走得更快。"},
    {"id": "golden_palanquin", "name": "金碟轿子", "en": "Golden Palanquin",
     "type": "luxury", "source": "mgp", "mgp_cost": 2000,
     "desc": "四个微型仙人掌帮你抬轿。金碟游乐场最奢华的出行方式。听说它们的鲇鱼同事每天都在拉价值两个亿的金轿子。好想这么有钱的活一次。"},
]

# ── 互动文案池(按宠物类型) ───────────────────────────
_BIRD = [
    "「{nick}」歪了歪头，用一只眼睛看着你。",
    "「{nick}」蹦到你头上，开始啄你的头发。……有点疼。",
    "「{nick}」在你肩上蹭了蹭脸，然后开始梳理自己的羽毛。",
    "「{nick}」突然唱了一首歌!……不太好听，但很有感情。",
    "「{nick}」从你手指上啄走了一颗面包屑。你都不知道自己手上有面包屑。",
    "「{nick}」展开翅膀在你面前转了一圈，好像在炫耀。",
    "「{nick}」飞到你鼻子前面悬停了一秒，然后轻轻啄了一下。——嘿!",
    "「{nick}」在你头顶做了一个窝。不知道用的什么材料。……你的头发?",
    "「{nick}」闭着眼睛站在你肩上打盹，偶尔晃一下差点摔下去。",
    "你把手伸出去，「{nick}」犹豫了一下——然后小心翼翼地站了上去。轻轻的。",
]
_REPTILE = [
    "「{nick}」沿着你的手臂慢慢爬到了肩膀上。凉凉的。",
    "「{nick}」在你的鞋子里缩成了一团。它觉得那里很安全。",
    "「{nick}」用尾巴缠住了你的手指。……是在撒娇吗?",
    "「{nick}」眯着眼睛趴在一块被太阳晒暖的石头上。看起来很幸福。",
    "「{nick}」突然抬头，伸出舌头舔了一下空气。然后又低下头了。",
    "「{nick}」爬到你的背包上面，占据了制高点，俯瞰一切。",
    "「{nick}」一动不动地盯着水面看了十分钟。然后打了个哈欠。",
    "你伸手碰了碰「{nick}」的壳/鳞片。它没躲。这就是信任。",
]
_MAMMAL = [
    "「{nick}」抱住了你的腿。不肯松手。你走路开始一瘸一拐的。",
    "「{nick}」趴在你腿上睡着了。你不敢动。",
    "「{nick}」叼着一颗不知道从哪找来的果子放在你面前。送你的?",
    "「{nick}」在你脚边打了个滚，肚皮朝天看着你。……要摸吗?",
    "「{nick}」用爪子拍了拍你的手——好像在说「再摸一下」。",
    "「{nick}」蹭了蹭你的脸。毛茸茸的。鼻子有点湿。",
    "「{nick}」打了一个很大的哈欠，露出了小小的牙齿。然后继续睡。",
    "「{nick}」听到了什么声音，耳朵竖了起来。然后——假警报。继续趴着。",
]
_AQUATIC = [
    "「{nick}」在桶/鱼缸里转了一个圈，溅了你一脸水。",
    "「{nick}」从水里探出头，看了看你在钓什么。然后缩回去了。",
    "「{nick}」在水面上吐了一串泡泡。你觉得那是它在说话。",
    "「{nick}」用尾巴拍了拍水面——啪! 你的衣服湿了一块。",
    "「{nick}」静静地漂在水面上，一动不动。像是在思考鱼生。",
    "「{nick}」追着桶里/缸里的光斑转圈圈。转了三圈之后头晕了。",
    "你把手指伸进水里，「{nick}」游过来蹭了蹭。痒痒的。",
    "「{nick}」从水里跳了出来!在空中翻了个身!然后——啪嗒。完美落水。",
]
_MAGICAL = [
    "「{nick}」在你头顶画了一个小小的光圈。好看，但没什么用。",
    "「{nick}」变成了半透明的，能看到它后面的风景。过了一会儿又变回来了。",
    "「{nick}」在你的鱼线上坐了一会儿。鱼线没有断——因为它几乎没有重量。",
    "「{nick}」碰了碰你的鼻子。一瞬间有星星在你眼前闪过。",
    "「{nick}」发出了微弱的光，照亮了你脚边的一小片地面。温暖的。",
    "「{nick}」飘到水面上方，盯着水里的鱼看。鱼也抬头看它。彼此好奇。",
    "「{nick}」在你身边转了一圈，留下了一串细小的光点。很快就消散了。",
    "你对「{nick}」吹了一口气。它被吹得飘了起来。然后慢慢飘回来了。",
]

_INTERACT_POOL = {
    "bird": _BIRD, "reptile": _REPTILE, "mammal": _MAMMAL,
    "aquatic": _AQUATIC, "magical": _MAGICAL,
}

# ── 坐骑旅行描写 ──────────────────────────────────────
_MOUNT_TRAVEL = {
    "chocobo": [
        "你骑上「{nick}」，它撒开腿就跑——走了三步开始啄路边的花。你拽了一下缰绳。",
        "「{nick}」小跑起来。风从耳边呼过——然后它突然停下来看蝴蝶。",
        "「{nick}」一路哼着歌带你出发。速度不快，但心情很好。",
    ],
    "boat": [
        "你跳上「{nick}」，拿起桨。水面上的倒影摇摇晃晃的。",
        "「{nick}」在水面上轻轻摇晃。你划了几下桨，出发了。",
        "你撑着「{nick}」沿水路出发。两岸的树从眼前慢慢滑过。",
    ],
    "reptile": [
        "你爬上「{nick}」的背。它慢慢地、慢慢地开始走。你有时间欣赏风景。",
        "「{nick}」迈出了第一步。然后是第二步。第三步的时候你差点睡着了。",
        "骑在「{nick}」背上很安心。它走得不快——但永远不会翻车。",
    ],
    "aquatic": [
        "你翻身骑上「{nick}」。它在水面上优雅地滑行，浪花在两侧散开。",
        "「{nick}」带着你在水上前进。你的脚被水花溅湿了——凉的!",
    ],
    "luxury": [
        "你坐进「{nick}」里。轿子微微一晃——出发了。你从帘子缝里看外面的风景。",
        "「{nick}」的轿夫们抬着你走在路上。路过的冒险者纷纷回头看。",
    ],
}

# ── 宠物对钓鱼的反应(钓到鱼时) ──────────────────────
_PET_CATCH_REACT = {
    "bird": [
        "「{nick}」激动地扑腾了一下翅膀!",
        "「{nick}」在你头上跳了两下——好像比你还高兴。",
        "「{nick}」对着你钓到的鱼叫了一声。……是在夸你吗?",
    ],
    "reptile": [
        "「{nick}」慢慢转过头，看了一眼你的鱼。然后又转回去了。就这样。",
        "「{nick}」的尾巴动了动。——对它来说这已经是很大的反应了。",
    ],
    "mammal": [
        "「{nick}」凑过来闻了闻你的鱼。鼻子皱了一下。",
        "「{nick}」欢快地在你脚边转圈圈!",
        "「{nick}」用爪子拍了拍你钓到的鱼。——不许抢!",
    ],
    "aquatic": [
        "「{nick}」从桶里探出头看了一眼。——你在钓它的同族……",
        "「{nick}」在水里转了个圈。可能是在给你鼓掌?",
    ],
    "magical": [
        "「{nick}」发出了微弱的光——好像在为你庆祝。",
        "「{nick}」在你的鱼上方飘了一圈，洒下一点点星尘。",
    ],
}


# ── 检查解锁 ──────────────────────────────────────
def check_new_pets(state: dict) -> list:
    """检查是否有新宠物可以解锁。返回 [(pet_dict, 原因), ...]。"""
    owned = set(state.get("pets", []))
    caught = state.get("caught", {})
    ocean_caught = state.get("ocean_caught", {})
    mgp = state.get("mgp", 0)
    new = []
    for p in PETS:
        if p["id"] in owned:
            continue
        if p["source"] == "fish" and p["fish"] in caught:
            new.append((p, f"钓到了 {p['fish']}"))
        elif p["source"] == "ach":
            req = p.get("req_caught", 0)
            req_oc = p.get("req_ocean", 0)
            if req and len(caught) >= req:
                new.append((p, f"图鉴达到 {req} 种"))
            elif req_oc and len(ocean_caught) >= req_oc:
                new.append((p, f"海钓图鉴达到 {req_oc} 种"))
        # MGP 不自动解锁，需要手动兑换
    # 实际解锁
    for p, reason in new:
        state.setdefault("pets", []).append(p["id"])
    return new


def check_new_mounts(state: dict) -> list:
    """检查是否有新坐骑可以解锁。返回 [(mount_dict, 原因), ...]。"""
    owned = set(state.get("mounts", []))
    caught = state.get("caught", {})
    ocean_caught = state.get("ocean_caught", {})
    new = []
    for m in MOUNTS:
        if m["id"] in owned:
            continue
        if m["source"] == "ach":
            req = m.get("req_caught", 0)
            req_oc = m.get("req_ocean", 0)
            if req and len(caught) >= req:
                new.append((m, f"图鉴达到 {req} 种"))
            elif req_oc and len(ocean_caught) >= req_oc:
                new.append((m, f"海钓图鉴达到 {req_oc} 种"))
    for m, reason in new:
        state.setdefault("mounts", []).append(m["id"])
    return new


def buy_pet(state: dict, pet_id: str) -> str | None:
    """MGP 兑换宠物。成功返回宠物名, 失败返回 None。"""
    p = next((x for x in PETS if x["id"] == pet_id), None)
    if not p or p["source"] != "mgp":
        return None
    if p["id"] in state.get("pets", []):
        return None
    cost = p.get("mgp_cost", 0)
    if state.get("mgp", 0) < cost:
        return None
    state["mgp"] -= cost
    state.setdefault("pets", []).append(p["id"])
    return p["name"]


def buy_mount(state: dict, mount_id: str) -> str | None:
    """MGP 兑换坐骑。"""
    m = next((x for x in MOUNTS if x["id"] == mount_id), None)
    if not m or m["source"] != "mgp":
        return None
    if m["id"] in state.get("mounts", []):
        return None
    cost = m.get("mgp_cost", 0)
    if state.get("mgp", 0) < cost:
        return None
    state["mgp"] -= cost
    state.setdefault("mounts", []).append(m["id"])
    return m["name"]


# ── 互动 ─────────────────────────────────────────
def interact(state: dict, rng: random.Random = None) -> str:
    """和当前宠物互动。"""
    pid = state.get("active_pet")
    if not pid:
        return "你身边没有宠物。用 summon <宠物名> 召唤一只!"
    p = next((x for x in PETS if x["id"] == pid), None)
    if not p:
        return "找不到这只宠物……"
    if rng is None:
        rng = random.Random()
    pool = _INTERACT_POOL.get(p["type"], _MAGICAL)
    nick = state.get("pet_names", {}).get(pid, p["name"])
    text = rng.choice(pool).format(nick=nick)
    return f"🐾 {text}"


def catch_reaction(state: dict, rng: random.Random) -> str:
    """钓到鱼时宠物的反应(20%概率触发)。"""
    pid = state.get("active_pet")
    if not pid or rng.random() > 0.20:
        return ""
    p = next((x for x in PETS if x["id"] == pid), None)
    if not p:
        return ""
    pool = _PET_CATCH_REACT.get(p["type"], _PET_CATCH_REACT["magical"])
    nick = state.get("pet_names", {}).get(pid, p["name"])
    text = rng.choice(pool).format(nick=nick)
    return f"\n   🐾 {text}"


def travel_text(state: dict, rng: random.Random) -> str:
    """移动时坐骑的旅行描写。"""
    mid = state.get("active_mount")
    if not mid:
        return ""
    m = next((x for x in MOUNTS if x["id"] == mid), None)
    if not m:
        return ""
    pool = _MOUNT_TRAVEL.get(m["type"], _MOUNT_TRAVEL.get("chocobo", [""]))
    nick = state.get("mount_names", {}).get(mid, m["name"])
    text = rng.choice(pool).format(nick=nick)
    return f"🐎 {text}\n"


def get_pet(pid: str):
    return next((x for x in PETS if x["id"] == pid), None)

def get_mount(mid: str):
    return next((x for x in MOUNTS if x["id"] == mid), None)

def find_pet(name: str):
    """按名字/id/中文名/英文名模糊匹配宠物。"""
    n = name.strip().lower()
    for p in PETS:
        if n in (p["id"], p["name"].lower(), p["en"].lower()):
            return p
    # 部分匹配
    for p in PETS:
        if n in p["name"].lower() or n in p["en"].lower():
            return p
    return None

def find_mount(name: str):
    n = name.strip().lower()
    for m in MOUNTS:
        if n in (m["id"], m["name"].lower(), m["en"].lower()):
            return m
    for m in MOUNTS:
        if n in m["name"].lower() or n in m["en"].lower():
            return m
    return None
