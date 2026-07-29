# -*- coding: utf-8 -*-
"""隔离探测 SiliconFlow/Qwen3-VL 视觉接口，打印完整错误。"""
from __future__ import annotations
import asyncio, os, sys, traceback
from pathlib import Path

os.environ["APP_ENV"] = "test"
os.environ["REDIS_URL"] = "memory://"
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.kernel.config import get_settings
import httpx

# 1x1 red pixel PNG
TINY = ("data:image/png;base64,"
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")


async def main() -> int:
    s = get_settings()
    key = s.vision_api_key or s.openai_api_key
    base = s.vision_base_url or s.openai_base_url or "https://api.openai.com/v1"
    model = s.vision_model or s.openai_model
    url = f"{base.rstrip('/')}/chat/completions"

    print("vision_base_url =", repr(s.vision_base_url))
    print("resolved base   =", repr(base))
    print("url             =", repr(url))
    print("model           =", repr(model))
    print("key repr        =", repr(key))           # repr 会暴露 \r \n 等隐藏字符
    print("key len         =", len(key) if key else 0)
    print("auth header repr=", repr(f"Bearer {key}"))

    body = {
        "model": model,
        "messages": [
            {"role": "user", "content": [
                {"type": "text", "text": "这张图是什么颜色？只答颜色。"},
                {"type": "image_url", "image_url": {"url": TINY}},
            ]},
        ],
        "max_tokens": 50,
        "temperature": 0.1,
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(url, json=body, headers=headers)
            print("HTTP", r.status_code)
            print("resp:", r.text[:800])
        return 0
    except Exception as e:
        print("!! EXC type:", type(e).__module__ + "." + type(e).__name__)
        print("!! EXC str :", str(e))
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
