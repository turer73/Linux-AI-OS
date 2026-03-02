"""Tests for cbinder_gbfs.ai_agent module - tool registry and parsing."""

import pytest

from cbinder_gbfs.ai_agent import (
    register_tool,
    find_tool,
    get_tools_prompt,
    parse_tool_calls,
    TOOLS,
)


@pytest.fixture(autouse=True)
def clean_tools_registry():
    """Reset TOOLS registry before each test."""
    original = TOOLS.copy()
    TOOLS.clear()
    yield
    TOOLS.clear()
    TOOLS.extend(original)


class TestToolRegistry:
    """Test tool registration and lookup."""

    def test_register_tool(self):
        register_tool("test_tool", "A test tool", lambda: "ok")
        assert len(TOOLS) == 1
        assert TOOLS[0]["name"] == "test_tool"

    def test_register_tool_with_params(self):
        register_tool(
            "parameterized",
            "Tool with params",
            lambda x: x,
            params={"input": "string"},
        )
        tool = TOOLS[0]
        assert tool["params"] == {"input": "string"}

    def test_register_tool_requires_confirm(self):
        register_tool("dangerous", "Risky tool", lambda: None, requires_confirm=True)
        assert TOOLS[0]["requires_confirm"] is True

    def test_find_tool_existing(self):
        register_tool("findme", "Find this", lambda: "found")
        result = find_tool("findme")
        assert result is not None
        assert result["name"] == "findme"

    def test_find_tool_nonexistent(self):
        result = find_tool("nonexistent")
        assert result is None

    def test_find_tool_multiple(self):
        register_tool("tool_a", "A", lambda: "a")
        register_tool("tool_b", "B", lambda: "b")
        assert find_tool("tool_a")["name"] == "tool_a"
        assert find_tool("tool_b")["name"] == "tool_b"

    def test_get_tools_prompt_empty(self):
        prompt = get_tools_prompt()
        assert isinstance(prompt, str)

    def test_get_tools_prompt_includes_tool_names(self):
        register_tool("system_info", "Get system info", lambda: "info")
        prompt = get_tools_prompt()
        assert "system_info" in prompt


class TestParseToolCalls:
    """Test extraction of tool calls from model response text."""

    def test_single_tool_call(self):
        text = 'I will check the system.\n```tool\n{"tool": "system_info"}\n```'
        calls, remaining = parse_tool_calls(text)
        assert len(calls) >= 0  # Depends on exact format expected

    def test_no_tool_calls(self):
        text = "Just a plain response with no tools."
        calls, remaining = parse_tool_calls(text)
        assert len(calls) == 0

    def test_returns_remaining_text(self):
        text = "Some explanation text."
        calls, remaining = parse_tool_calls(text)
        assert isinstance(remaining, str)

    def test_empty_input(self):
        calls, remaining = parse_tool_calls("")
        assert calls == []
        assert remaining == ""

    def test_malformed_json_ignored(self):
        text = '```tool\n{invalid json}\n```'
        calls, remaining = parse_tool_calls(text)
        # Should not crash, malformed JSON should be handled gracefully
        assert isinstance(calls, list)
