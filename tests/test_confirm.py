import sys
from unittest.mock import patch
import pytest
from ternexar.confirm import (
    ConfirmationMode,
    confirm_engine,
    is_interactive_terminal,
    prompt_medium_confirmation,
)


def test_confirm_minimal():
    result = confirm_engine.evaluate("ls")
    assert result.mode == ConfirmationMode.MINIMAL_CONFIRMATION.value


def test_confirm_standard():
    result = confirm_engine.evaluate("pip install rich")
    assert result.mode == ConfirmationMode.STANDARD_CONFIRMATION.value


def test_confirm_strong():
    result = confirm_engine.evaluate("sudo rm file")
    assert result.mode == ConfirmationMode.STRONG_CONFIRMATION.value


def test_confirm_refused():
    result = confirm_engine.evaluate("rm -rf /")
    assert result.mode == ConfirmationMode.REFUSED.value


def test_is_interactive_terminal(monkeypatch):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    assert is_interactive_terminal() is True

    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    assert is_interactive_terminal() is False


@pytest.mark.parametrize("affirmative", ["y", "Y", "yes", "YES", " y "])
def test_prompt_medium_confirmation_accepted(monkeypatch, affirmative):
    monkeypatch.setattr("ternexar.confirm.is_interactive_terminal", lambda: True)
    monkeypatch.setattr("typer.prompt", lambda *args, **kwargs: affirmative)
    assert prompt_medium_confirmation("pip install rich", "Package Installation") is True


@pytest.mark.parametrize("declined", ["n", "N", "no", "NO", "", "foo", "maybe", "123"])
def test_prompt_medium_confirmation_declined(monkeypatch, declined):
    monkeypatch.setattr("ternexar.confirm.is_interactive_terminal", lambda: True)
    monkeypatch.setattr("typer.prompt", lambda *args, **kwargs: declined)
    assert prompt_medium_confirmation("pip install rich", "Package Installation") is False


def test_prompt_medium_confirmation_non_interactive(monkeypatch):
    monkeypatch.setattr("ternexar.confirm.is_interactive_terminal", lambda: False)
    assert prompt_medium_confirmation("pip install rich", "Package Installation") is False


def test_prompt_medium_confirmation_eof(monkeypatch):
    monkeypatch.setattr("ternexar.confirm.is_interactive_terminal", lambda: True)

    def raise_eof(*args, **kwargs):
        raise EOFError()

    monkeypatch.setattr("typer.prompt", raise_eof)
    assert prompt_medium_confirmation("pip install rich", "Package Installation") is False


def test_prompt_medium_confirmation_keyboard_interrupt(monkeypatch):
    monkeypatch.setattr("ternexar.confirm.is_interactive_terminal", lambda: True)

    def raise_ki(*args, **kwargs):
        raise KeyboardInterrupt()

    monkeypatch.setattr("typer.prompt", raise_ki)
    assert prompt_medium_confirmation("pip install rich", "Package Installation") is False
