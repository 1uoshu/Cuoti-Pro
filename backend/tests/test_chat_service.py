"""Tests for app.kernel.chat.service — ChatSession & ChatMessage CRUD + serializers."""
from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.kernel.chat.service import (
    add_message,
    create_session,
    delete_session,
    get_message_count,
    get_session,
    list_messages,
    list_sessions,
    rename_session,
    serialize_message,
    serialize_session,
    touch_session,
)
from app.kernel.database import Base, SessionLocal, engine
from app.kernel.models import ChatMessage, ChatSession, User


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True, scope="session")
def _create_tables():
    """Ensure all ORM tables exist in the test database."""
    Base.metadata.create_all(bind=engine)


@pytest.fixture(autouse=True)
def _clean_chat_data():
    """Delete all chat data before each test for isolation."""
    with SessionLocal() as db:
        db.query(ChatMessage).delete()
        db.query(ChatSession).delete()
        db.commit()
    yield


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TEST_USER_ID = 1


def _ensure_user(db: Session) -> None:
    """Insert a test user if not already present."""
    if db.get(User, TEST_USER_ID) is None:
        db.add(User(id=TEST_USER_ID, username="testuser", password_hash="x", nickname="Test"))
        db.commit()


def _make_session(user_id: int = TEST_USER_ID, **kwargs) -> ChatSession:
    with SessionLocal() as db:
        _ensure_user(db)
        return create_session(db, user_id=user_id, **kwargs)


def _make_messages(session_id: int, count: int) -> list[ChatMessage]:
    with SessionLocal() as db:
        msgs = []
        for i in range(count):
            msgs.append(
                add_message(db, session_id=session_id, role="student", content=f"msg-{i}")
            )
        return msgs


# ---------------------------------------------------------------------------
# Session CRUD tests
# ---------------------------------------------------------------------------


def test_create_session():
    with SessionLocal() as db:
        _ensure_user(db)
        session = create_session(db, user_id=TEST_USER_ID, title="测试会话")
        assert session.id > 0
        assert session.title == "测试会话"
        assert session.user_id == TEST_USER_ID


def test_list_sessions_empty():
    with SessionLocal() as db:
        _ensure_user(db)
        result = list_sessions(db, user_id=TEST_USER_ID)
        assert result == []


def test_list_sessions_ordered_by_last_active():
    s1 = _make_session(title="first")
    s2 = _make_session(title="second")

    with SessionLocal() as db:
        result = list_sessions(db, user_id=TEST_USER_ID)
        assert len(result) == 2
        # s2 was created after s1, so it should appear first
        assert result[0].id == s2.id
        assert result[1].id == s1.id


def test_get_session_returns_session():
    created = _make_session(title="findme")
    with SessionLocal() as db:
        found = get_session(db, session_id=created.id, user_id=TEST_USER_ID)
        assert found is not None
        assert found.id == created.id
        assert found.title == "findme"


def test_get_session_wrong_user_returns_none():
    created = _make_session()
    with SessionLocal() as db:
        result = get_session(db, session_id=created.id, user_id=9999)
        assert result is None


def test_rename_session():
    created = _make_session(title="old")
    with SessionLocal() as db:
        renamed = rename_session(db, session_id=created.id, user_id=TEST_USER_ID, title="new")
        assert renamed is not None
        assert renamed.title == "new"


def test_rename_nonexistent_returns_none():
    with SessionLocal() as db:
        result = rename_session(db, session_id=999999, user_id=TEST_USER_ID, title="x")
        assert result is None


def test_delete_session():
    created = _make_session()
    with SessionLocal() as db:
        assert delete_session(db, session_id=created.id, user_id=TEST_USER_ID) is True
    with SessionLocal() as db:
        assert get_session(db, session_id=created.id, user_id=TEST_USER_ID) is None


def test_delete_nonexistent_returns_false():
    with SessionLocal() as db:
        assert delete_session(db, session_id=999999, user_id=TEST_USER_ID) is False


def test_delete_session_cascades_messages():
    created = _make_session()
    _make_messages(created.id, 3)

    with SessionLocal() as db:
        count_before = get_message_count(db, session_id=created.id)
        assert count_before == 3

    with SessionLocal() as db:
        delete_session(db, session_id=created.id, user_id=TEST_USER_ID)

    with SessionLocal() as db:
        count_after = get_message_count(db, session_id=created.id)
        assert count_after == 0


# ---------------------------------------------------------------------------
# Message CRUD tests
# ---------------------------------------------------------------------------


def test_add_message():
    created = _make_session()
    with SessionLocal() as db:
        msg = add_message(db, session_id=created.id, role="student", content="hello")
        assert msg.id > 0
        assert msg.role == "student"
        assert msg.content == "hello"
        assert msg.session_id == created.id


def test_add_message_updates_last_active():
    created = _make_session()
    original_last_active = created.last_active_at

    with SessionLocal() as db:
        add_message(db, session_id=created.id, role="agent", content="hi")

    with SessionLocal() as db:
        refreshed = db.get(ChatSession, created.id)
        assert refreshed.last_active_at >= original_last_active


def test_add_message_invalid_role_raises():
    created = _make_session()
    with SessionLocal() as db:
        with pytest.raises(ValueError, match="Invalid role"):
            add_message(db, session_id=created.id, role="invalid_role", content="x")


def test_list_messages_empty():
    created = _make_session()
    with SessionLocal() as db:
        result = list_messages(db, session_id=created.id, user_id=TEST_USER_ID)
        assert result == []


def test_list_messages_with_pagination():
    created = _make_session()
    _make_messages(created.id, 5)

    with SessionLocal() as db:
        all_msgs = list_messages(db, session_id=created.id, user_id=TEST_USER_ID)
        assert len(all_msgs) == 5

        first_two = list_messages(db, session_id=created.id, user_id=TEST_USER_ID, limit=2)
        assert len(first_two) == 2
        assert first_two[0].content == "msg-0"
        assert first_two[1].content == "msg-1"

        skipped = list_messages(db, session_id=created.id, user_id=TEST_USER_ID, limit=2, offset=2)
        assert len(skipped) == 2
        assert skipped[0].content == "msg-2"
        assert skipped[1].content == "msg-3"


def test_list_messages_wrong_user_returns_empty():
    created = _make_session()
    _make_messages(created.id, 2)

    with SessionLocal() as db:
        result = list_messages(db, session_id=created.id, user_id=9999)
        assert result == []


# ---------------------------------------------------------------------------
# Serializer tests
# ---------------------------------------------------------------------------


def test_serialize_session():
    created = _make_session(title="ser-test")
    with SessionLocal() as db:
        session = db.get(ChatSession, created.id)
        data = serialize_session(session)

        assert data["id"] == session.id
        assert data["title"] == "ser-test"
        assert data["created_at"] is not None
        assert data["updated_at"] is not None
        assert data["last_active_at"] is not None


def test_serialize_message():
    created = _make_session()
    with SessionLocal() as db:
        msg = add_message(
            db,
            session_id=created.id,
            role="agent",
            content="payload-test",
            card_type="quiz",
            card_payload={"q": 1},
            step_id="step-1",
        )
        data = serialize_message(msg)

        assert data["id"] == msg.id
        assert data["session_id"] == created.id
        assert data["role"] == "agent"
        assert data["content"] == "payload-test"
        assert data["card_type"] == "quiz"
        assert data["card_payload"] == {"q": 1}
        assert data["step_id"] == "step-1"
        assert data["created_at"] is not None


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------


def test_get_message_count():
    created = _make_session()
    with SessionLocal() as db:
        assert get_message_count(db, session_id=created.id) == 0

    _make_messages(created.id, 4)

    with SessionLocal() as db:
        assert get_message_count(db, session_id=created.id) == 4
