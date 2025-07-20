"""A runner, an office file and a stocked office for the command line suite."""

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


@pytest.fixture
def stocked(run: Callable[..., Result]) -> Callable[..., Result]:
    """An office file with a carrier, a rig and the corridor map on it."""
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
    return run
