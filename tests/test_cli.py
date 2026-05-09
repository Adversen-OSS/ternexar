import pytest
from typer.testing import CliRunner
from ternexar.main import app

runner = CliRunner()

def test_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "TERNEXAR v1.9.0" in result.stdout
def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "safety-first AI command center" in result.stdout

def test_doctor_smoke():
    # tx doctor might fail if ollama is missing, but it should exit gracefully
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0 or result.exit_code == 1
    # Check for the banner or some diagnostic output
    assert "TERNEXAR" in result.stdout
