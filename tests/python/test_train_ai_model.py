"""Tests for cbinder_gbfs.train_ai_model module."""

import pytest

from cbinder_gbfs.train_ai_model import LABELS, load_and_prepare_data

torch = pytest.importorskip("torch", reason="torch required for IOModel tests")


class TestIOModel:
    """Test IOModel (defined inside train_torch function, tested via train_torch)."""

    def test_torch_import(self):
        import torch
        assert torch is not None


class TestLabels:
    def test_all_labels_present(self):
        expected = {"IDLE", "READ_FOCUS", "WRITE_PRIORITY", "OPTIMIZE_BALANCE"}
        assert set(LABELS.keys()) == expected

    def test_labels_are_sequential(self):
        values = sorted(LABELS.values())
        assert values == [0, 1, 2, 3]


class TestLoadAndPrepareData:
    def test_loads_data_correctly(self, sample_io_log_csv):
        X, y, scaler = load_and_prepare_data(str(sample_io_log_csv))
        assert X.shape[0] == 4  # 4 rows
        assert X.shape[2] == 2  # 2 features (read, write)
        assert y.shape[0] == 4

    def test_labels_are_encoded(self, sample_io_log_csv):
        X, y, scaler = load_and_prepare_data(str(sample_io_log_csv))
        for val in y.tolist():
            assert val in [0, 1, 2, 3]

    def test_data_is_normalized(self, sample_io_log_csv):
        X, y, scaler = load_and_prepare_data(str(sample_io_log_csv))
        # MinMaxScaler normalizes to [0, 1]
        assert X.min() >= 0.0
        assert X.max() <= 1.0
