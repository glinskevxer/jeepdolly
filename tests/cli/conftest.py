"""A runner, an office file and a stocked office for the command line suite.

The stocked office is built once for the whole session and copied per test. It
takes eleven commands to build and there are about a hundred and twenty tests
that want it, which was most of the suite's running time and none of its value.
The copy goes through sqlite's own backup rather than the filesystem, so a write
ahead log left over from the build cannot come across half applied.
"""

from collections.abc import Callable
from pathlib import Path

import pytest
from click.testing import CliRunner, Result

from jeepdolly.cli.main import main
from jeepdolly.store.backup import back_up


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


def _stock(run: Callable[..., Result]) -> None:
    """Put a carrier, a rig and the corridor map on an office file."""
    run(
        "carrier",
        "add",
        "--code",
        "VANCE",
        "--name",
        "Vance Heavy Haul",
        "--usdot",
        "1184062",
        "--state",
        "MT",
    )
    for key in ("JCT-A", "JCT-B", "JCT-C", "JCT-D"):
        run("road", "node", "--code", key, "--name", key.lower(), "--county", "Missoula")
    for key, start, end, route, length in (
        ("SEG-AB", "JCT-A", "JCT-B", "US-12", "12.00"),
        ("SEG-BC", "JCT-B", "JCT-C", "US-12", "8.50"),
        ("SEG-BD", "JCT-B", "JCT-D", "SR-200", "31.00"),
    ):
        run(
            "road",
            "segment",
            "--code",
            key,
            "--start",
            start,
            "--end",
            end,
            "--route",
            route,
            "--miles",
            length,
        )
    run(
        "road",
        "segment",
        "--code",
        "SEG-CD",
        "--start",
        "JCT-C",
        "--end",
        "JCT-D",
        "--route",
        "US-12",
        "--miles",
        "6.00",
        "--posted",
        "48,000",
    )
    run("rig", "build", "--carrier", "VANCE", "--name", "3S2")


@pytest.fixture(scope="session")
def stocked_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One stocked office file, built once for the whole session."""
    path = tmp_path_factory.mktemp("template") / "office.sqlite3"
    runner = CliRunner()

    def go(*args: str) -> Result:
        result = runner.invoke(main, ["-f", str(path), *args])
        assert result.exit_code == 0, result.output
        return result

    go("init")
    _stock(go)
    return path


@pytest.fixture
def stocked(runner: CliRunner, tmp_path: Path, stocked_template: Path) -> Callable[..., Result]:
    """A fresh copy of the stocked office file, per test."""
    path = tmp_path / "office.sqlite3"
    back_up(stocked_template, path)

    def go(*args: str) -> Result:
        return runner.invoke(main, ["-f", str(path), *args])

    return go
