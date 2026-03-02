"""Tests for cbinder_gbfs.ai_kernel_bridge module - ioctl macros and constants."""

import sys
import pytest

if sys.platform == "win32":
    pytest.skip("ai_kernel_bridge requires Linux (fcntl)", allow_module_level=True)

from cbinder_gbfs.ai_kernel_bridge import (
    _IO,
    _IOR,
    _IOW,
    _IOWR,
    GOV_NAMES,
    GOV_BY_NAME,
    STATE_NAMES,
    KernelModuleNotLoaded,
    KernelPermissionDenied,
)


class TestIoctlMacros:
    """Test Linux ioctl number generation macros."""

    def test_io_generates_correct_number(self):
        # _IO(type, nr) = (type << 8) | nr
        result = _IO(ord("A"), 0)
        assert result == (ord("A") << 8) | 0

    def test_io_different_numbers(self):
        r1 = _IO(ord("A"), 1)
        r2 = _IO(ord("A"), 2)
        assert r1 != r2

    def test_ior_includes_size_and_direction(self):
        result = _IOR(ord("A"), 1, 64)
        assert result != _IO(ord("A"), 1)
        assert isinstance(result, int)

    def test_iow_includes_size_and_direction(self):
        result = _IOW(ord("A"), 1, 64)
        assert result != _IO(ord("A"), 1)
        assert result != _IOR(ord("A"), 1, 64)

    def test_iowr_combines_read_write(self):
        result = _IOWR(ord("A"), 1, 64)
        assert result != _IOR(ord("A"), 1, 64)
        assert result != _IOW(ord("A"), 1, 64)

    def test_io_magic_a_matches_kernel(self):
        # AI_IOC_MAGIC = 'A' (0x41) in ai_ioctl.h
        magic = ord("A")
        cmd0 = _IO(magic, 0)
        cmd1 = _IO(magic, 1)
        assert (cmd0 >> 8) & 0xFF == magic
        assert cmd1 - cmd0 == 1


class TestGovernorMappings:
    """Test governor name <-> id mappings are consistent."""

    def test_gov_names_has_entries(self):
        assert len(GOV_NAMES) > 0

    def test_gov_by_name_has_entries(self):
        assert len(GOV_BY_NAME) > 0

    def test_forward_reverse_consistency(self):
        for gov_id, name in GOV_NAMES.items():
            assert GOV_BY_NAME[name] == gov_id

    def test_reverse_forward_consistency(self):
        for name, gov_id in GOV_BY_NAME.items():
            assert GOV_NAMES[gov_id] == name

    def test_known_governors_exist(self):
        expected = {"ondemand", "performance", "powersave"}
        actual = set(GOV_BY_NAME.keys())
        assert expected.issubset(actual), f"Missing governors: {expected - actual}"


class TestStateNames:
    """Test state name mappings."""

    def test_state_names_has_entries(self):
        assert len(STATE_NAMES) > 0

    def test_state_values_are_strings(self):
        for state_id, name in STATE_NAMES.items():
            assert isinstance(name, str)
            assert len(name) > 0


class TestExceptions:
    """Test custom exception classes."""

    def test_kernel_not_loaded_is_exception(self):
        with pytest.raises(KernelModuleNotLoaded):
            raise KernelModuleNotLoaded("Module not loaded")

    def test_kernel_permission_denied_is_exception(self):
        with pytest.raises(KernelPermissionDenied):
            raise KernelPermissionDenied("Permission denied")

    def test_exception_message(self):
        msg = "/dev/ai_ctl not found"
        exc = KernelModuleNotLoaded(msg)
        assert msg in str(exc)
