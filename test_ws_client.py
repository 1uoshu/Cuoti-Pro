#!/usr/bin/env python3
"""WebSocket客户端测试 - 模拟前端完整流程"""
import websocket
import json
import requests
import time
import threading

TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZXhwIjoxNzg1Mzc3Mjg5LCJqdGkiOiJXN1pnai1hZUtnWl9WUElCM2JNUE9lRGtOWEtfdVBDUiIsInR5cCI6ImFjY2VzcyJ9.jLl2jREHf0pwIFV7kyTs7-2uM2gnC5g1Holm_H6HySA"
BASE_URL = "http://localhost:8000"

def test_complete_flow():
    print("=== Starting Complete Upload + Chat Test ===\n")

    # 1. 创建新会话
    print("1. Creating new session...")
    resp = requests.post(
        f"{BASE_URL}/api/agent/sessions?title=WS测试会话",
        headers={"Authorization": f"Bearer {TOKEN}"}
    )
    session_id = resp.json()["data"]["id"]
    print(f"   [OK] Created session {session_id}\n")

    # 2. 建立WebSocket连接
    print("2. Connecting WebSocket...")
    ws_url = f"ws://localhost:8000/api/agent/ws?session_id={session_id}&token={TOKEN}"

    messages_received = []

    def on_message(ws, message):
        data = json.loads(message)
        msg_type = data.get("type", "unknown")
        messages_received.append(data)
        print(f"   <- Received: {msg_type}")
        if msg_type == "chat.text_delta":
            print(f"      Delta: {data.get('data', {}).get('delta', '')}", end='', flush=True)

    def on_error(ws, error):
        print(f"   ! WebSocket error: {error}")

    def on_close(ws, close_status_code, close_msg):
        print(f"\n   WebSocket closed: {close_status_code} {close_msg}")

    def on_open(ws):
        print("   [OK] WebSocket connected\n")

        # 等待welcome消息
        time.sleep(1)

        # 3. 上传作业
        print("3. Uploading assignment...")
        with open(r"C:\Users\宇怀\Desktop\作业2.png", "rb") as f:
            upload_resp = requests.post(
                f"{BASE_URL}/api/agent/upload",
                headers={"Authorization": f"Bearer {TOKEN}"},
                files={"file": f},
                data={"subject": "数学", "session_id": session_id}
            )
        upload_data = upload_resp.json()
        print(f"   [OK] Upload result: assignment_id={upload_data['data']['assignment_id']}\n")

        # 4. 发送WebSocket消息触发Agent
        print("4. Sending message to trigger Agent...")
        message = {
            "type": "chat.message",
            "content": "[用户上传了文件，未附带文字说明]"
        }
        ws.send(json.dumps(message))
        print(f"   [OK] Message sent\n")

        print("5. Waiting for Agent responses...")

    ws = websocket.WebSocketApp(ws_url,
                                on_open=on_open,
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)

    # 在后台线程运行WebSocket
    wst = threading.Thread(target=ws.run_forever)
    wst.daemon = True
    wst.start()

    # 等待30秒接收消息
    time.sleep(30)

    print(f"\n\n=== Test Complete ===")
    print(f"Total messages received: {len(messages_received)}")

    ws.close()

if __name__ == "__main__":
    test_complete_flow()
