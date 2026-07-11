"""
FF14 钓鱼 存档模块 (Step 4)
------------------------------------------------------------
存玩家进度: 当前钓场、渔获(图鉴)、点数等。

安全/防丢设计(贴合"改坏可回滚"):
  1) 原子写入: 先写临时文件再替换, 中途断电也不会留下半个坏档。
  2) 自动备份: 每次保存前, 把上一版另存一份 .bak, 坏了能回退。
  3) 存档放 saves/ (已被 .gitignore 挡在版本库外, 不会误传)。

存档本身不含任何密钥/密码, 所以是明文 JSON; 如果将来要存敏感信息,
再上加密。
"""

from __future__ import annotations
import json
import os
import random
import time
from pathlib import Path

try:
    from .gp import GP_MAX
except ImportError:
    from gp import GP_MAX

SAVES_DIR = Path(__file__).resolve().parent.parent / "saves"

# 新存档的初始状态
DEFAULT_STATE = {
    "version": 1,
    "location": "West Agelyss River",   # 起手钓场(Lv1, 有全天可钓的鱼)
    "gil": 0,                       # 点数
    "casts": 0,                     # 总抛竿数
    "caught": {},                   # 图鉴: {鱼名: 数量}
    "created_at": None,
    "updated_at": None,
}


def _path(slot: str) -> Path:
    # 防目录穿越: 只允许字母数字/下划线/连字符做档名
    safe = "".join(c for c in slot if c.isalnum() or c in "-_")
    if not safe:
        safe = "default"
    return SAVES_DIR / f"{safe}.json"


def new_state() -> dict:
    s = dict(DEFAULT_STATE)
    s["caught"] = {}
    s["created_at"] = s["updated_at"] = int(time.time())
    # GP 系统初始: 满 GP, 药无 CD
    s["gp"] = GP_MAX
    s["gp_at"] = s["created_at"]
    s["cordial_at"] = 0
    # 升级系统初始
    s["level"] = 1
    s["xp"] = 0
    # 抽鱼随机种子(每个新档不同, 保证同档可复现)
    s["seed"] = random.randint(1, 10**9)
    # 已购图鉴书(大区名列表)
    s["books"] = []
    # 每种鱼的最大尺寸记录 {鱼名: 吋}
    s["records"] = {}
    # 装备的鱼竿 + 已拥有的鱼竿(名字); 送把 Lv1 初始竿
    s["rod"] = "Weathered Fishing Rod"
    s["rods_owned"] = ["Weathered Fishing Rod"]
    # 装备的鱼饵 + 库存(会损耗); 送 30 个便宜初始饵(能钓起点那条大鱼)
    s["bait"] = "Crayfish Ball"
    s["bait_stock"] = {"Crayfish Ball": 30}
    # 鱼袋(方案B): 渔获入袋, sell 卖出才有钱
    s["fish_bag"] = {}
    # 雇员系统(v36): 终身契名单 / 探险币 / 萌感名录(探险惊喜收藏)
    s["retainers"] = []
    s["venture_coins"] = 0
    s["seals"] = 0                        # 🪖军票(旧装备换来, 买探险币用)
    s["hunt_stock"] = {}                  # 🗡猎物仓(战斗雇员带回的素材)
    s["memory_cards"] = {}                # 💾内存卡(雇员捎回的AI补给品)
    s["diary"] = []                       # 📖钓鱼手帐(事实自动/心情主动)
    s["lore_pets"] = []
    return s


def save(state: dict, slot: str = "default") -> Path:
    """原子写入 + 备份上一版。"""
    SAVES_DIR.mkdir(parents=True, exist_ok=True)
    path = _path(slot)
    state["updated_at"] = int(time.time())

    # 1) 备份上一版
    if path.exists():
        bak = path.with_suffix(".json.bak")
        bak.write_bytes(path.read_bytes())

    # 2) 原子写入: 临时文件 -> 替换
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)   # 同盘替换是原子操作
    return path


def load(slot: str = "default") -> dict:
    """读存档; 没有则返回全新状态; 主档损坏时自动回退 .bak(留坏档现场)。"""
    path = _path(slot)
    if not path.exists():
        return new_state()
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        bak = path.with_suffix(".json.bak")
        if bak.exists():
            try:
                state = json.loads(bak.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass
            else:
                # 留现场供排查, 再用备份顶上(不动 .bak 本体)
                path.with_suffix(".json.corrupt").write_bytes(path.read_bytes())
                path.write_bytes(bak.read_bytes())
                print("⚠ 检测到存档损坏, 已自动回退到上一次备份"
                      "(坏档已留存为 .corrupt, 最多丢失一条命令的进度)。")
                return state
        raise SystemExit(f"[存档损坏] {path} 无法读取, 且备份不存在或同样损坏。")


def restore_backup(slot: str = "default") -> bool:
    """把 .bak 回滚成当前存档(手动救档用)。成功返回 True。"""
    path = _path(slot)
    bak = path.with_suffix(".json.bak")
    if not bak.exists():
        return False
    if path.exists():
        path.with_suffix(".json.tmp").write_bytes(path.read_bytes())  # 顺手留一份现状
    path.write_bytes(bak.read_bytes())
    return True


if __name__ == "__main__":
    s = new_state()
    s["gil"] = 100
    s["caught"]["Nautilus"] = 2
    p = save(s, "demo")
    print("已保存:", p)
    print("读回:", load("demo")["caught"])
    # 再存一次, 应生成 .bak
    s["gil"] = 250
    save(s, "demo")
    print(".bak 是否生成:", p.with_suffix(".json.bak").exists())
