"""Tests for cbinder_gbfs.ai_dev_setup module."""

import pytest
from unittest.mock import patch, MagicMock

from cbinder_gbfs.ai_dev_setup import (
    command_exists,
    get_total_ram_mb,
    get_free_disk_gb,
    get_cpu_info,
    check_system,
    is_ollama_installed,
    list_ollama_models,
    has_model,
    is_vscode_installed,
    is_claude_code_installed,
    build_parser,
)


class TestCommandExists:
    def test_finds_python(self):
        assert command_exists("python3") or command_exists("python")

    def test_nonexistent_returns_false(self):
        assert not command_exists("nonexistent_cmd_xyz_99999")


class TestSystemChecks:
    def test_ram_positive(self):
        assert get_total_ram_mb() > 0

    def test_disk_non_negative(self):
        assert get_free_disk_gb("/") >= 0

    def test_cpu_info_keys(self):
        info = get_cpu_info()
        assert "physical_cores" in info
        assert "logical_threads" in info
        assert info["logical_threads"] > 0

    @patch("cbinder_gbfs.ai_dev_setup.get_total_ram_mb", return_value=8192)
    @patch("cbinder_gbfs.ai_dev_setup.get_free_disk_gb", return_value=20)
    @patch("cbinder_gbfs.ai_dev_setup.detect_gpu", return_value="")
    def test_check_system_passes(self, _gpu, _disk, _ram):
        assert check_system() is True

    @patch("cbinder_gbfs.ai_dev_setup.get_total_ram_mb", return_value=2048)
    @patch("cbinder_gbfs.ai_dev_setup.get_free_disk_gb", return_value=20)
    @patch("cbinder_gbfs.ai_dev_setup.detect_gpu", return_value="")
    def test_check_system_fails_low_ram(self, _gpu, _disk, _ram):
        assert check_system() is False

    @patch("cbinder_gbfs.ai_dev_setup.get_total_ram_mb", return_value=8192)
    @patch("cbinder_gbfs.ai_dev_setup.get_free_disk_gb", return_value=2)
    @patch("cbinder_gbfs.ai_dev_setup.detect_gpu", return_value="")
    def test_check_system_fails_low_disk(self, _gpu, _disk, _ram):
        assert check_system() is False


class TestOllamaDetection:
    @patch("cbinder_gbfs.ai_dev_setup.command_exists", return_value=True)
    def test_installed(self, _):
        assert is_ollama_installed() is True

    @patch("cbinder_gbfs.ai_dev_setup.command_exists", return_value=False)
    def test_not_installed(self, _):
        assert is_ollama_installed() is False

    @patch("cbinder_gbfs.ai_dev_setup.is_ollama_installed", return_value=False)
    def test_list_empty_without_ollama(self, _):
        assert list_ollama_models() == []

    def test_has_model(self):
        with patch("cbinder_gbfs.ai_dev_setup.list_ollama_models",
                    return_value=["qwen2.5-coder:3b", "linux-ai-coder:latest"]):
            assert has_model("linux-ai-coder") is True
            assert has_model("nonexistent") is False


class TestToolDetection:
    @patch("cbinder_gbfs.ai_dev_setup.command_exists", return_value=False)
    def test_vscode_not_found(self, _):
        assert is_vscode_installed() is False

    @patch("cbinder_gbfs.ai_dev_setup.command_exists", return_value=False)
    def test_claude_not_found(self, _):
        assert is_claude_code_installed() is False

    @patch("cbinder_gbfs.ai_dev_setup.command_exists", return_value=True)
    def test_claude_found(self, _):
        assert is_claude_code_installed() is True


class TestArgParser:
    def test_install(self):
        args = build_parser().parse_args(["install"])
        assert args.command == "install"

    def test_status(self):
        args = build_parser().parse_args(["status"])
        assert args.command == "status"

    def test_model_pull(self):
        args = build_parser().parse_args(["model-pull"])
        assert args.command == "model-pull"

    def test_model_pull_custom(self):
        args = build_parser().parse_args(["model-pull", "--model", "codellama:7b"])
        assert args.model == "codellama:7b"

    def test_configure(self):
        args = build_parser().parse_args(["configure"])
        assert args.command == "configure"

    def test_no_command(self):
        args = build_parser().parse_args([])
        assert args.command is None
