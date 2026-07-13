"""
FF14 钓鱼 存档随身模块 (v43.2)
------------------------------------------------------------
把整份存档打包成一段可复制的文字("存档串"), 或从存档串恢复。

为什么需要它:
  有些 AI 的运行环境(ChatGPT 代码沙箱、claude.ai 的新对话等)
  每次对话结束会清空文件, 进度会丢。离开前 `export` 导出存档串
  交给玩家保存; 下次开局 `import <串>` 原地满血复活。
  存档串也可以发给朋友, 让她的 AI 接着玩你的档。

格式(设计目标: 粘贴不怕换行、坏了能发现、绝不悄悄吃坏档):
  FF14FISH1.<base64(zlib(存档JSON))>.<crc32 十六进制>
  - 解析时自动剔除混入的空白/换行(聊天软件爱自动折行);
    甚至把 export 的整段回复原样粘进来也能自动认出其中的串。
  - CRC 校验: 复制缺了一截会明确报错, 不会解出半个坏档。
  - 串里只有游戏进度, 不含任何密钥/密码/个人信息。
"""
from __future__ import annotations

import base64
import json
import re
import zlib

MAGIC = "FF14FISH1"                     # 版本前缀; 未来格式升级换 FF14FISH2
_WRAP = 76                              # base64 折行宽度(邮件传统, 看着舒服)
# 在任意文字里认出存档串: 前缀 + base64 段(允许夹空白) + 8 位 CRC
_BLOB_RE = re.compile(
    MAGIC + r"\.[A-Za-z0-9+/=\s]+\.[0-9a-fA-F]{8}")


class BlobError(ValueError):
    """存档串无法解析时抛出, 携带给玩家看的中文说明。"""


def export_blob(state: dict) -> str:
    """状态字典 → 存档串(多行, 复制整段即可)。"""
    raw = json.dumps(state, ensure_ascii=False,
                     separators=(",", ":")).encode("utf-8")
    comp = zlib.compress(raw, 9)
    b64 = base64.b64encode(comp).decode("ascii")
    crc = format(zlib.crc32(comp) & 0xFFFFFFFF, "08x")
    wrapped = "\n".join(b64[i:i + _WRAP] for i in range(0, len(b64), _WRAP))
    return f"{MAGIC}.\n{wrapped}\n.{crc}"


def import_blob(text: str) -> dict:
    """任意粘贴文本 → 状态字典; 认不出/损坏则抛 BlobError(带原因)。"""
    text = text or ""
    m = _BLOB_RE.search(text)
    if not m:
        # 没匹配上时区分两种情况, 给更有用的报错
        if MAGIC in "".join(text.split()):
            raise BlobError("存档串不完整: 结尾的校验段缺失, 多半是复制时被截断了, 请重新完整复制。")
        raise BlobError(f"没找到存档串(应包含以 {MAGIC}. 开头、8 位校验码结尾的一段)。")
    compact = "".join(m.group(0).split())          # 剔除全部空白
    body = compact[len(MAGIC) + 1:]
    b64, crc_hex = body.rsplit(".", 1)
    try:
        comp = base64.b64decode(b64, validate=True)
    except Exception:
        raise BlobError("存档串里混入了无法解码的字符, 请重新完整复制一次。")
    if format(zlib.crc32(comp) & 0xFFFFFFFF, "08x") != crc_hex.lower():
        raise BlobError("校验不通过: 存档串在复制/传输中缺了或多了内容, 原档未被改动。")
    try:
        state = json.loads(zlib.decompress(comp).decode("utf-8"))
    except Exception:
        raise BlobError("解压失败: 存档串损坏, 原档未被改动。")
    if not isinstance(state, dict) or "location" not in state:
        raise BlobError("内容不像一份钓鱼存档(缺关键字段), 原档未被改动。")
    return state
