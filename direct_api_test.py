#!/usr/bin/env python3
"""直接通过HTTP POST模拟Agent处理（绕过WebSocket）"""
import requests
import json

TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZXhwIjoxNzg1Mzc3Mjg5LCJqdGkiOiJXN1pnai1hZUtnWl9WUElCM2JNUE9lRGtOWEtfdVBDUiIsInR5cCI6ImFjY2VzcyJ9.jLl2jREHf0pwIFV7kyTs7-2uM2gnC5g1Holm_H6HySA"
BASE_URL = "http://localhost:8000"
SESSION_ID = 12

# 直接在数据库插入一条student消息来触发Agent
import subprocess

print("Inserting student message directly into database...")
cmd = [
    "docker", "exec", "smart-learning-agent-mysql-1",
    "mysql", "-u", "root", "-psmart-learning-demo-root-password",
    "-e", f"""INSERT INTO smart_learning_agent.chat_messages (session_id, role, content, card_type, created_at, updated_at)
             VALUES ({SESSION_ID}, 'student', '[用户上传了文件，未附带文字说明]', NULL, NOW(), NOW());"""
]

result = subprocess.run(cmd, capture_output=True, text=True)
if "Warning" not in result.stderr and not result.returncode:
    print("✓ Message inserted")
else:
    print(f"Failed: {result.stderr}")

print("\nWaiting for Agent to process (批改任务应该已在后台运行)...")
print("Checking messages after 3 seconds...")

import time
time.sleep(3)

# 查看消息
cmd = [
    "docker", "exec", "smart-learning-agent-mysql-1",
    "mysql", "-u", "root", "-psmart-learning-demo-root-password",
    "--default-character-set=utf8mb4",
    "-e", f"SELECT id, role, LEFT(content, 80) as content FROM smart_learning_agent.chat_messages WHERE session_id={SESSION_ID} ORDER BY id;"
]

result = subprocess.run(cmd, capture_output=True, text=True)
print("\nMessages in session:", result.stdout)

# 检查调试文件
cmd = ["docker", "exec", "smart-learning-agent-backend-1", "cat", "/tmp/convert_history_debug.txt"]
result = subprocess.run(cmd, capture_output=True, text=True)
if result.stdout:
    print("\nDebug file content:")
    print(result.stdout)
else:
    print("\nNo debug file found - convert_history_to_api was NOT called!")
