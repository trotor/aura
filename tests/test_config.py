"""Testit ajonaikaiselle konfiguraatiolle (#135)."""

from aura.config import is_readonly


def test_readonly_false_when_unset() -> None:
    assert is_readonly(env={}) is False


def test_readonly_true_for_truthy_values() -> None:
    for val in ("1", "true", "TRUE", "yes", "on", " 1 "):
        assert is_readonly(env={"AURA_READONLY": val}) is True, val


def test_readonly_false_for_falsy_values() -> None:
    for val in ("0", "false", "no", "off", ""):
        assert is_readonly(env={"AURA_READONLY": val}) is False, val
