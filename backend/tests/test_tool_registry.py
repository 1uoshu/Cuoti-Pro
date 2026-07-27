"""Tests for ToolSpec and ToolRegistry in app.kernel.agent.tools."""

import pytest

from app.kernel.agent.tools import SideEffect, ToolRegistry, ToolSpec


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tool(
    name: str = "Plugin::Tool",
    description: str = "A test tool",
    short_intent: str = "测试工具",
    side_effect: SideEffect = SideEffect.READ,
    requires_confirmation: bool = False,
    handler=None,
    **kwargs,
) -> ToolSpec:
    """Factory for ToolSpec with sensible defaults."""
    if handler is None:
        handler = lambda: None
    return ToolSpec(
        name=name,
        description=description,
        short_intent=short_intent,
        side_effect=side_effect,
        requires_confirmation=requires_confirmation,
        handler=handler,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# ToolRegistry tests
# ---------------------------------------------------------------------------

def test_register_and_get():
    """Registering a tool makes it retrievable via get()."""
    # Arrange
    registry = ToolRegistry()
    tool = _make_tool(name="Report::Generate")

    # Act
    registry.register(tool)

    # Assert
    assert registry.get("Report::Generate") is tool


def test_get_nonexistent_returns_none():
    """get() returns None when the requested tool name does not exist."""
    # Arrange
    registry = ToolRegistry()

    # Act
    result = registry.get("NoSuch::Tool")

    # Assert
    assert result is None


def test_list_all_empty():
    """An empty registry returns an empty list from list_all()."""
    # Arrange
    registry = ToolRegistry()

    # Act
    result = registry.list_all()

    # Assert
    assert result == []


def test_list_all_returns_all_tools():
    """list_all() returns every registered tool."""
    # Arrange
    registry = ToolRegistry()
    t1 = _make_tool(name="A::One")
    t2 = _make_tool(name="B::Two")
    t3 = _make_tool(name="C::Three")
    for t in (t1, t2, t3):
        registry.register(t)

    # Act
    result = registry.list_all()

    # Assert
    assert len(result) == 3
    assert set(result) == {t1, t2, t3}


def test_list_by_side_effect():
    """list_by_side_effect() filters tools correctly by their side-effect level."""
    # Arrange
    registry = ToolRegistry()
    read_tool = _make_tool(name="Cache::Lookup", side_effect=SideEffect.READ)
    write_tool = _make_tool(name="DB::Save", side_effect=SideEffect.WRITE)
    send_tool = _make_tool(
        name="Email::Send",
        side_effect=SideEffect.SEND,
        requires_confirmation=True,
    )
    for t in (read_tool, write_tool, send_tool):
        registry.register(t)

    # Act & Assert
    assert registry.list_by_side_effect(SideEffect.READ) == [read_tool]
    assert registry.list_by_side_effect(SideEffect.WRITE) == [write_tool]
    assert registry.list_by_side_effect(SideEffect.SEND) == [send_tool]


def test_describe_all_returns_dicts():
    """describe_all() returns a list of dicts with the expected keys."""
    # Arrange
    registry = ToolRegistry()
    tool = _make_tool(
        name="Quiz::Start",
        description="Start a quiz",
        short_intent="开始测验",
        side_effect=SideEffect.WRITE,
        requires_confirmation=False,
        autonomous=True,
        preconditions=("logged_in",),
    )
    registry.register(tool)

    # Act
    result = registry.describe_all()

    # Assert
    assert len(result) == 1
    entry = result[0]
    assert entry["name"] == "Quiz::Start"
    assert entry["description"] == "Start a quiz"
    assert entry["short_intent"] == "开始测验"
    assert entry["side_effect"] == "write"
    assert entry["requires_confirmation"] is False
    assert entry["autonomous"] is True
    assert entry["preconditions"] == ["logged_in"]


def test_duplicate_register_is_idempotent():
    """Registering two tools with the same name is a no-op (idempotent)."""
    # Arrange
    registry = ToolRegistry()
    tool = _make_tool(name="Dup::Tool")
    registry.register(tool)

    # Act — second register should not raise
    registry.register(_make_tool(name="Dup::Tool"))

    # Assert — still only one tool
    assert len(registry.list_all()) == 1


def test_send_requires_confirmation():
    """Creating a ToolSpec with side_effect=SEND and requires_confirmation=False raises ValueError."""
    # Arrange / Act / Assert
    with pytest.raises(ValueError, match="requires_confirmation=False"):
        _make_tool(
            name="Mail::Blast",
            side_effect=SideEffect.SEND,
            requires_confirmation=False,
        )


def test_send_with_confirmation_allowed():
    """A ToolSpec with side_effect=SEND and requires_confirmation=True is valid."""
    # Arrange / Act
    tool = _make_tool(
        name="Mail::Notify",
        side_effect=SideEffect.SEND,
        requires_confirmation=True,
    )

    # Assert
    assert tool.side_effect == SideEffect.SEND
    assert tool.requires_confirmation is True


def test_read_does_not_require_confirmation():
    """A ToolSpec with side_effect=READ and requires_confirmation=False is valid."""
    # Arrange / Act
    tool = _make_tool(
        name="Profile::View",
        side_effect=SideEffect.READ,
        requires_confirmation=False,
    )

    # Assert
    assert tool.side_effect == SideEffect.READ
    assert tool.requires_confirmation is False


def test_tool_spec_frozen():
    """ToolSpec is frozen; attempting to mutate an attribute raises."""
    # Arrange
    tool = _make_tool()

    # Act / Assert
    with pytest.raises(AttributeError):
        tool.name = "Changed::Name"


def test_register_multiple_different_tools():
    """Each registered tool is independent; modifying one does not affect others."""
    # Arrange
    registry = ToolRegistry()
    t1 = _make_tool(name="Alpha::One", description="first")
    t2 = _make_tool(name="Beta::Two", description="second")
    t3 = _make_tool(name="Gamma::Three", description="third")

    # Act
    for t in (t1, t2, t3):
        registry.register(t)

    # Assert -- each is retrievable independently
    assert registry.get("Alpha::One").description == "first"
    assert registry.get("Beta::Two").description == "second"
    assert registry.get("Gamma::Three").description == "third"
    assert len(registry.list_all()) == 3
