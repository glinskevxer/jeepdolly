import pytest

from jeepdolly import __version__
from jeepdolly.tools.check_version import (
    PYPROJECT,
    declared_version,
    main,
    problems,
    well_formed,
)


def a_project(tmp_path, version: str) -> None:
    """A pretend project naming a version."""
    (tmp_path / PYPROJECT).write_text(
        f'[project]\nname = "x"\nversion = "{version}"\n', encoding="utf-8"
    )


def test_the_two_versions_agree():
    assert problems() == []


def test_main_passes_over_the_project():
    assert main() == 0


def test_the_declared_version_is_read():
    assert declared_version() == __version__


def test_the_package_is_past_one_point_zero():
    major, minor, patch = (int(part) for part in __version__.split("."))
    assert (major, minor, patch) >= (1, 1, 0)


@pytest.mark.parametrize("version", ["1.0.0", "0.1.0", "12.3.45"])
def test_three_numbers_are_well_formed(version):
    assert well_formed(version)


@pytest.mark.parametrize("version", ["1.0", "1.0.0rc1", "1.0.0.1", "", "one"])
def test_anything_else_is_not_well_formed(version):
    assert not well_formed(version)


def test_a_disagreement_is_reported(tmp_path):
    a_project(tmp_path, "9.9.9")
    found = problems(tmp_path)
    assert any("and the package says" in line for line in found)


def test_a_malformed_declared_version_is_reported(tmp_path):
    a_project(tmp_path, "1.0.0rc1")
    found = problems(tmp_path)
    assert any("which is not three numbers" in line for line in found)


def test_a_project_naming_no_version_is_reported(tmp_path):
    (tmp_path / PYPROJECT).write_text('[project]\nname = "x"\n', encoding="utf-8")
    found = problems(tmp_path)
    assert any("names no version" in line for line in found)


def test_a_matching_project_reports_nothing(tmp_path):
    a_project(tmp_path, __version__)
    assert problems(tmp_path) == []


def test_the_command_line_prints_the_same_version():
    from click.testing import CliRunner

    from jeepdolly.cli.main import main as cli

    result = CliRunner().invoke(cli, ["--version"])
    assert __version__ in result.output
