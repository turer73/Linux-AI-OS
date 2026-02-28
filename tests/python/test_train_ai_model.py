"""Tests for cbinder_gbfs.train_ai_model module."""

import pytest

from cbinder_gbfs.train_ai_model import IOModel, LABELS, load_and_prepare_data


class TestIOModel:
    def test_model_creation(self):
        model = IOModel()
        assert model is not None

    def test_model_custom_sizes(self):
        model = IOModel(input_size=3, hidden_size=32, output_size=2)
        assert model is not None

    def test_forward_pass_shape(self):
        import torch
        model = IOModel(input_size=2, hidden_size=64, output_size=4)
        # Batch of 4, sequence length 1, 2 features
        x = torch.randn(4, 1, 2)
        output = model(x)
        assert output.shape == (4, 4)

    def test_output_is_differentiable(self):
        import torch
        model = IOModel()
        x = torch.randn(2, 1, 2, requires_grad=True)
        output = model(x)
        loss = output.sum()
        loss.backward()
        assert x.grad is not None


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
