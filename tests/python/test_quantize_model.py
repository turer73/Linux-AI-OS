"""Tests for quantize_model.py - Model compression utilities."""

import os
import pytest
from unittest.mock import patch, MagicMock


# ─── Argument parsing ────────────────────────────────────────────────────────


class TestQuantizeArgParsing:
    def test_default_args(self):
        from cbinder_gbfs.quantize_model import main
        # main() exits early when model file doesn't exist
        with patch("sys.argv", ["quantize_model"]):
            with patch("cbinder_gbfs.quantize_model.os.path.exists", return_value=False):
                main()  # Should not crash, prints "not found" message

    def test_custom_input_arg(self):
        from cbinder_gbfs.quantize_model import main
        with patch("sys.argv", ["quantize_model", "--input", "custom.pkl"]):
            with patch("cbinder_gbfs.quantize_model.os.path.exists", return_value=False):
                main()  # Should handle gracefully

    def test_onnx_format_arg(self):
        from cbinder_gbfs.quantize_model import main
        with patch("sys.argv", ["quantize_model", "--format", "onnx"]):
            with patch("cbinder_gbfs.quantize_model.os.path.exists", return_value=False):
                main()


# ─── Constants ────────────────────────────────────────────────────────────────


class TestQuantizeConstants:
    def test_default_paths(self):
        from cbinder_gbfs.quantize_model import (
            SKLEARN_MODEL, SCALER_PATH, TFLITE_OUTPUT, ONNX_OUTPUT
        )
        assert SKLEARN_MODEL == "ai_model.pkl"
        assert SCALER_PATH == "ai_scaler.pkl"
        assert TFLITE_OUTPUT == "ai_model_q8.tflite"
        assert ONNX_OUTPUT == "ai_model.onnx"


# ─── quantize_sklearn_to_tflite (mocked) ─────────────────────────────────────


class TestQuantizeTFLite:
    def test_returns_false_without_tensorflow(self, capsys):
        """The function should print error and return False when TF is missing."""
        from cbinder_gbfs.quantize_model import quantize_sklearn_to_tflite

        # Patch the import inside the function to raise ImportError
        original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__

        def mock_import(name, *args, **kwargs):
            if name == "tensorflow":
                raise ImportError("No module named 'tensorflow'")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            result = quantize_sklearn_to_tflite("fake.pkl", "fake_scaler.pkl", "out.tflite")
        assert result is False
        out = capsys.readouterr().out
        assert "TensorFlow" in out


# ─── quantize_sklearn_to_onnx (mocked) ───────────────────────────────────────


class TestQuantizeONNX:
    def test_returns_false_without_skl2onnx(self, capsys):
        """The function should print error and return False when skl2onnx is missing."""
        from cbinder_gbfs.quantize_model import quantize_sklearn_to_onnx

        original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__

        def mock_import(name, *args, **kwargs):
            if name == "skl2onnx":
                raise ImportError("No module named 'skl2onnx'")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            result = quantize_sklearn_to_onnx("fake.pkl", "fake_scaler.pkl", "out.onnx")
        assert result is False
        out = capsys.readouterr().out
        assert "skl2onnx" in out
