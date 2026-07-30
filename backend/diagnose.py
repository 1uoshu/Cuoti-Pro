"""诊断脚本：检查数据库状态、测试服务层、模拟完整的会话创建流程"""
import sys
sys.path.insert(0, 'd:/Microcontroller/agent/Cuoti-Pro-main/Cuoti-Pro-main/backend')

import traceback
from sqlalchemy import text
from app.kernel.database import SessionLocal, engine
from app.kernel.models import User, ChatSession, ChatMessage
from app.kernel.chat.service import create_session, add_message, serialize_session

print("=" * 60)
print("1. 检查数据库表结构")
print("=" * 60)

with engine.connect() as conn:
    # 检查 users 表
    result = conn.execute(text("SELECT COUNT(*) as cnt FROM users")).fetchone()
    user_count = result[0]
    print(f"✓ users 表: {user_count} 行")

    if user_count == 0:
        print("  ⚠ WARNING: users表为空，需要先注册用户才能创建会话")
    else:
        users = conn.execute(text("SELECT id, username, email, role FROM users LIMIT 3")).fetchall()
        for u in users:
            print(f"  - id={u[0]}, username={u[1]}, email={u[2]}, role={u[3]}")

    # 检查 chat_sessions 表结构
    schema = conn.execute(text("SELECT sql FROM sqlite_master WHERE name='chat_sessions'")).fetchone()[0]
    if 'id INTEGER' in schema:
        print("✓ chat_sessions.id: INTEGER (正确)")
    elif 'id VARCHAR' in schema:
        print("✗ chat_sessions.id: VARCHAR (错误！应该是INTEGER)")
        print("  运行以下命令修复:")
        print("  cd backend && .venv/Scripts/python.exe _fix_chat_tables.py")
        sys.exit(1)

    # 检查 chat_messages 表结构
    schema = conn.execute(text("SELECT sql FROM sqlite_master WHERE name='chat_messages'")).fetchone()[0]
    if 'session_id INTEGER' in schema:
        print("✓ chat_messages.session_id: INTEGER (正确)")
    elif 'session_id VARCHAR' in schema:
        print("✗ chat_messages.session_id: VARCHAR (错误！应该是INTEGER)")
        sys.exit(1)

    sessions_count = conn.execute(text("SELECT COUNT(*) FROM chat_sessions")).fetchone()[0]
    messages_count = conn.execute(text("SELECT COUNT(*) FROM chat_messages")).fetchone()[0]
    print(f"✓ chat_sessions: {sessions_count} 行")
    print(f"✓ chat_messages: {messages_count} 行")

print("\n" + "=" * 60)
print("2. 测试服务层 (create_session)")
print("=" * 60)

try:
    with SessionLocal() as db:
        # 获取第一个用户
        user = db.query(User).first()
        if not user:
            print("✗ 无法测试: users表为空")
            print("\n解决方案:")
            print("  1. 启动后端: cd backend && .venv/Scripts/python.exe -m uvicorn app.main:app --reload")
            print("  2. 访问 http://127.0.0.1:8000/docs")
            print("  3. 使用 POST /api/auth/register 注册一个测试账号")
            sys.exit(1)

        print(f"使用测试用户: id={user.id}, username={user.username}")

        # 测试创建会话
        print("\n调用 create_session(db, user_id={}, title='诊断测试会话')".format(user.id))
        session = create_session(db, user_id=user.id, title="诊断测试会话")
        print(f"✓ 创建成功: session_id={session.id}")
        print(f"  序列化结果: {serialize_session(session)}")

        # 测试添加消息
        print("\n调用 add_message(session_id={}, role='student', content='hello')".format(session.id))
        msg = add_message(db, session_id=session.id, role="student", content="hello")
        print(f"✓ 添加消息成功: message_id={msg.id}")

        # 清理测试数据
        db.delete(msg)
        db.delete(session)
        db.commit()
        print("✓ 清理测试数据完成")

except Exception as e:
    print(f"\n✗ 服务层测试失败:")
    print(f"  错误类型: {type(e).__name__}")
    print(f"  错误消息: {e}")
    print("\n完整堆栈:")
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("3. 诊断结果")
print("=" * 60)
print("✓ 数据库表结构正确")
print("✓ 服务层功能正常")
print("\n如果前端仍然500错误，可能原因:")
print("  1. 后端服务未启动 → 运行 start_and_test.bat")
print("  2. 前端未登录/token无效 → 401而非500，检查浏览器Console")
print("  3. 后端有其他运行时错误 → 查看后端控制台的完整错误堆栈")
print("\n下一步:")
print("  1. 运行 start_and_test.bat 启动服务")
print("  2. 访问 http://localhost:5173")
print("  3. 登录后尝试创建会话")
print("  4. 如果还是500，复制后端控制台的完整错误信息")
