"""Tests for cbinder_gbfs.ai_help module - help system structure and content."""

import pytest

from cbinder_gbfs.ai_help import TOPICS, strip_rich_tags


class TestStripRichTags:
    """Test Rich markup tag removal."""

    def test_removes_bold(self):
        assert strip_rich_tags("[bold]text[/bold]") == "text"

    def test_removes_color(self):
        result = strip_rich_tags("[green]success[/green]")
        assert result == "success"

    def test_removes_nested_tags(self):
        result = strip_rich_tags("[bold][red]error[/red][/bold]")
        assert result == "error"

    def test_preserves_plain_text(self):
        text = "no tags here"
        assert strip_rich_tags(text) == text

    def test_handles_empty_string(self):
        assert strip_rich_tags("") == ""

    def test_removes_style_tags(self):
        result = strip_rich_tags("[dim]faded[/dim]")
        assert result == "faded"


class TestTopicsStructure:
    """Test help topics dictionary structure."""

    def test_topics_is_dict(self):
        assert isinstance(TOPICS, dict)

    def test_topics_not_empty(self):
        assert len(TOPICS) > 0

    def test_all_values_are_strings(self):
        for key, value in TOPICS.items():
            assert isinstance(value, str), f"Topic '{key}' value is not a string"

    def test_all_keys_are_strings(self):
        for key in TOPICS:
            assert isinstance(key, str)

    def test_known_topics_exist(self):
        expected_topics = {"komutlar", "kurulum", "sorun"}
        actual = set(TOPICS.keys())
        for topic in expected_topics:
            assert topic in actual, f"Expected topic '{topic}' not found"

    def test_topics_have_content(self):
        for key, value in TOPICS.items():
            assert len(value.strip()) > 10, f"Topic '{key}' has too little content"

    def test_no_duplicate_keys(self):
        keys = list(TOPICS.keys())
        assert len(keys) == len(set(keys))
