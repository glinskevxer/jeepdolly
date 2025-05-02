"""A runner and an office file for the command line suite."""

from collections.abc import Callable
from pathlib import Path

import pytest
from click.testing import CliRunner, Result

from jeepdolly.cli.main import main


@pytest.fixture
def runner() -> CliRunner:
    """Click's own runner."""
    return CliRunner()


@pytest.fixture
def office_file(tmp_path: Path, runner: CliRunner) -> Path:
    """A created office file, ready for commands."""
    path = tmp_path / "office.sqlite3"
    result = runner.invoke(main, ["-f", str(path), "init"])
    assert result.exit_code == 0, result.output
    return path


@pytest.fixture
def run(runner: CliRunner, office_file: Path) -> Callable[..., Result]:
    """Run a command against the created office file."""

    def go(*args: str) -> Result:
        return runner.invoke(main, ["-f", str(office_file), *args])

    return go
