#!/usr/bin/env python3
"""测试作业上传和Agent处理的完整流程"""
import asyncio
import websockets
import json
import requests

TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZXhwIjoxNzg1Mzc3Mjg5LCJqdGkiOiJXN1pnai1hZUtnWl9WUElCM2JNUE9lRGtOWEtfdVBDUiIsInR5cCI6ImFjY2VzcyJ9.jLl2jREHf0pwIFV7kyTs7-2uM2gnC5g1Holm_H6HySA"
BASE_URL = "http://localhost:8000"

async def test_upload_and_chat():
    # 1. 创建新会话
    print("1. Creating new session...")
    resp = requests.post(
        f"{BASE_URL}/api/agent/sessions?title=测试会话",
        headers={"Authorization": f"Bearer {TOKEN}"}
    )
    session_data = resp.json()
    session_id = session_data["data"]["id"]
    print(f"   Created session {session_id}")

    # 2. 上传作业
    print("2. Uploading assignment...")
    with open(r"C:\Users\宇怀\Desktop\作业2.png", "rb") as f:
        resp = requests.post(
            f"{BASE_URL}/api/agent/upload",
            headers={"Authorization": f"Bearer {TOKEN}"},
            files={"file": f},
            data={"subject": "数学", "session_id": session_id}
        )
    upload_data = resp.json()
    print(f"   Upload result: {upload_data}")

    # 3. 建立WebSocket连接
    print("3. Connecting to WebSocket...")
    ws_url = f"ws://localhost:8000/api/agent/ws?session_id={session_id}&token={TOKEN}"

    async with websockets.connect(ws_url) as websocket:
        print("   WebSocket connected")

        # 接收welcome消息
        welcome = await websocket.recv()
        print(f"   Received: {json.loads(welcome)['type']}")

        # 4. 发送消息触发Agent处理
        print("4. Sending message to trigger Agent...")
        message = {
            "type": "chat.message",
            "content": "[用户上传了文件，未附带文字说明]"
        }
        await websocket.send(json.dumps(message))
        print("   Message sent")

        # 5. 接收Agent响应
        print("5. Receiving Agent responses...")
        response_count = 0
        try:
            while response_count < 20:  # 最多接收20条消息
                response = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                data = json.loads(response)
                print(f"   [{response_count}] {data.get('type', 'unknown')}: {str(data.get('data', ''))[:100]}")
                response_count += 1

                if data.get('type') == 'plan.done':
                    print("   Agent processing complete!")
                    break
        except asyncio.TimeoutError:
            print("   Timeout waiting for response")

if __name__ == "__main__":
    asyncio.run(test_upload_and_chat())
