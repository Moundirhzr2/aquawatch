"""Security regressions for the local container verification CLI."""

import importlib.util
from pathlib import Path
from unittest.mock import Mock

import pytest


@pytest.fixture
def checker(monkeypatch, tmp_path):
    path = Path(__file__).resolve().parents[1] / "scripts" / "check_containers.py"
    spec = importlib.util.spec_from_file_location("check_containers", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    return module


@pytest.mark.parametrize(
    "arguments",
    [
        ["--docker", "python"],
        ["--docker=/tmp/untrusted-program", "--config-only"],
        ["--docker", "cmd.exe /c echo injected"],
        ["--config-only", "; echo injected"],
        ["--config"],
    ],
)
def test_untrusted_cli_arguments_cannot_start_processes(checker, monkeypatch, arguments):
    run = Mock()
    monkeypatch.setattr(checker.subprocess, "run", run)
    with pytest.raises(SystemExit) as error:
        checker.main(arguments)
    assert error.value.code == 2
    run.assert_not_called()
    assert not (checker.ROOT / "runtime").exists()


def test_config_only_uses_docker_without_starting_or_removing_containers(checker, monkeypatch):
    run = Mock()
    monkeypatch.setattr(checker.subprocess, "run", run)
    checker.main(["--config-only"])
    commands = [call.args[0] for call in run.call_args_list]
    assert len(commands) == 2
    assert commands[0] == ["docker", "compose", "version"]
    assert commands[1][:2] == ["docker", "compose"]
    assert commands[1][-4:] == ["--profile", "analytics", "config", "--quiet"]
    assert all(not call.kwargs.get("shell", False) for call in run.call_args_list)
    assert not list((checker.ROOT / "runtime").iterdir())
