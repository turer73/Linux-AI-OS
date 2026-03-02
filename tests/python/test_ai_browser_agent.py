"""Tests for ai_browser_agent.py - Web API automation agents."""

import os
import json
import pytest
from unittest.mock import patch, MagicMock

from cbinder_gbfs.ai_browser_agent import (
    api_call,
    get_token,
    info,
    warn,
    error,
    VercelAgent,
    CloudflareAgent,
)


# ─── api_call ─────────────────────────────────────────────────────────────────


class TestApiCall:
    def test_returns_parsed_json(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"status": "ok"}'

        with patch("cbinder_gbfs.ai_browser_agent.subprocess.run", return_value=mock_result):
            result = api_call("GET", "https://api.example.com/test", "token123")
        assert result == {"status": "ok"}

    def test_returns_none_on_curl_failure(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""

        with patch("cbinder_gbfs.ai_browser_agent.subprocess.run", return_value=mock_result):
            result = api_call("GET", "https://api.example.com/test", "token123")
        assert result is None

    def test_returns_none_on_timeout(self):
        import subprocess
        with patch("cbinder_gbfs.ai_browser_agent.subprocess.run",
                   side_effect=subprocess.TimeoutExpired(cmd="curl", timeout=30)):
            result = api_call("GET", "https://api.example.com/test", "token123")
        assert result is None

    def test_returns_none_on_invalid_json(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "not json at all"

        with patch("cbinder_gbfs.ai_browser_agent.subprocess.run", return_value=mock_result):
            result = api_call("GET", "https://api.example.com/test", "token123")
        assert result is None

    def test_returns_none_on_curl_not_found(self):
        with patch("cbinder_gbfs.ai_browser_agent.subprocess.run",
                   side_effect=FileNotFoundError):
            result = api_call("GET", "https://api.example.com/test", "token123")
        assert result is None

    def test_includes_data_payload(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"created": true}'

        with patch("cbinder_gbfs.ai_browser_agent.subprocess.run", return_value=mock_result) as mock_run:
            api_call("POST", "https://api.example.com/create", "token123",
                     data={"name": "test"})
            args = mock_run.call_args[0][0]
            assert "-d" in args
            payload = args[args.index("-d") + 1]
            assert json.loads(payload) == {"name": "test"}

    def test_auth_header_included(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{}'

        with patch("cbinder_gbfs.ai_browser_agent.subprocess.run", return_value=mock_result) as mock_run:
            api_call("GET", "https://api.example.com/test", "my_secret_token")
            args = mock_run.call_args[0][0]
            assert "Authorization: Bearer my_secret_token" in " ".join(args)


# ─── get_token ────────────────────────────────────────────────────────────────


class TestGetToken:
    def test_returns_token_from_env(self, monkeypatch):
        monkeypatch.setenv("TEST_TOKEN", "abc123")
        assert get_token("TEST_TOKEN") == "abc123"

    def test_returns_empty_on_missing_env(self, monkeypatch):
        monkeypatch.delenv("NONEXISTENT_VAR", raising=False)
        assert get_token("NONEXISTENT_VAR") == ""

    def test_prints_warning_on_missing(self, monkeypatch, capsys):
        monkeypatch.delenv("MISSING_TOKEN", raising=False)
        get_token("MISSING_TOKEN")
        out = capsys.readouterr().out
        assert "MISSING_TOKEN" in out


# ─── Output helpers ───────────────────────────────────────────────────────────


class TestOutputHelpers:
    def test_info_prints(self, capsys):
        info("test message")
        assert "test message" in capsys.readouterr().out

    def test_warn_prints(self, capsys):
        warn("warning message")
        assert "warning message" in capsys.readouterr().out

    def test_error_prints(self, capsys):
        error("error message")
        assert "error message" in capsys.readouterr().out


# ─── VercelAgent ──────────────────────────────────────────────────────────────


class TestVercelAgent:
    def test_init_reads_token(self, monkeypatch):
        monkeypatch.setenv("VERCEL_TOKEN", "vtoken123")
        agent = VercelAgent()
        assert agent.token == "vtoken123"

    def test_list_projects_no_token(self, monkeypatch, capsys):
        monkeypatch.delenv("VERCEL_TOKEN", raising=False)
        agent = VercelAgent()
        agent.list_projects()
        # Should silently return (token is empty)

    def test_list_projects_success(self, monkeypatch):
        monkeypatch.setenv("VERCEL_TOKEN", "test")
        agent = VercelAgent()
        with patch("cbinder_gbfs.ai_browser_agent.api_call") as mock_api:
            mock_api.return_value = {
                "projects": [
                    {"name": "myapp", "framework": "nextjs", "updatedAt": "2026-01-01"}
                ]
            }
            agent.list_projects()
            mock_api.assert_called_once()

    def test_list_deployments_with_project(self, monkeypatch):
        monkeypatch.setenv("VERCEL_TOKEN", "test")
        agent = VercelAgent()
        with patch("cbinder_gbfs.ai_browser_agent.api_call") as mock_api:
            mock_api.return_value = {"deployments": []}
            agent.list_deployments(project="proj123", limit=3)
            url_arg = mock_api.call_args[0][1]
            assert "proj123" in url_arg
            assert "limit=3" in url_arg

    def test_api_url_correct(self):
        assert VercelAgent.API == "https://api.vercel.com"


# ─── CloudflareAgent ─────────────────────────────────────────────────────────


class TestCloudflareAgent:
    def test_init_reads_token(self, monkeypatch):
        monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "cftoken")
        agent = CloudflareAgent()
        assert agent.token == "cftoken"

    def test_list_zones_no_token(self, monkeypatch):
        monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)
        agent = CloudflareAgent()
        agent.list_zones()  # Should not crash

    def test_list_zones_success(self, monkeypatch):
        monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "test")
        agent = CloudflareAgent()
        with patch("cbinder_gbfs.ai_browser_agent.api_call") as mock_api:
            mock_api.return_value = {
                "success": True,
                "result": [
                    {"name": "example.com", "status": "active", "id": "z123"}
                ]
            }
            agent.list_zones()
            mock_api.assert_called_once()

    def test_api_url_correct(self):
        assert CloudflareAgent.API == "https://api.cloudflare.com/client/v4"


# ─── Constants ────────────────────────────────────────────────────────────────


class TestConstants:
    def test_bold_defined(self):
        from cbinder_gbfs.ai_browser_agent import BOLD
        assert BOLD == "\033[1m"

    def test_color_codes(self):
        from cbinder_gbfs.ai_browser_agent import GREEN, YELLOW, RED, NC
        assert "\033[" in GREEN
        assert "\033[" in YELLOW
        assert "\033[" in RED
        assert NC == "\033[0m"
