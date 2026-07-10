"""
AI 驱动入口 —— 给 AI 朋友玩的单条命令接口
============================================================
每次调用 = 发一条命令 + 打印一条回复。进度自动存, 每位玩家隔离。

用法:
    python ai_play.py <玩家名> <命令...>

例:
    python ai_play.py sakura              # 不带命令 = 看当前处境(look)
    python ai_play.py sakura look
    python ai_play.py sakura cast
    python ai_play.py sakura "goto Moraby Bay"
    python ai_play.py sakura bag

说明:
- <玩家名> 请用英文/数字(如 sakura、alice、bot1);每位玩家进度存在
  saves/<玩家名>.json, 互相隔离、自动备份, 关了再开接着玩。
- 命令一览见 AI_GUIDE.md, 或运行:  python ai_play.py <玩家名> help
- 天气/时间按真实时钟本地推算 —— "你此刻钓不到的鱼, AI 也钓不到"。
"""

import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from engine.game import Game


def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    player = args[0]
    command = " ".join(args[1:]).strip() or "look"
    try:
        g = Game(slot=player)          # 按玩家名分槽(防目录穿越), 各自隔离
        print(g.cmd(command))
        return 0
    except BrokenPipeError:
        return 0                       # 输出被管道截断(如 | head), 静默退出
    except Exception as e:
        try:
            print(f"[出错] {type(e).__name__}: {e}")
        except BrokenPipeError:
            pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
