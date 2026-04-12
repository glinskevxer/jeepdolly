import pytest

from jeepdolly.tools.check_pins import (
    CONSTRAINTS,
    PYPROJECT,
    WORKFLOW,
    declared,
    main,
    pins,
    problems,
)


def a_project(
    tmp_path, constraints: str, workflow: str = "python -m pip install -c constraints.txt x"
) -> None:
    """A pretend project tree with the three files the check reads."""
    (tmp_path / CONSTRAINTS).write_text(constraints, encoding="utf-8")
    (tmp_path / PYPROJECT).write_text(
        '[build-system]\nrequires = ["hatchling==1.27.0"]\n'
        '[project]\nname = "x"\ndependencies = ["click==8.1.8"]\n',
        encoding="utf-8",
    )
    made = tmp_path / WORKFLOW
    made.parent.mkdir(parents=True, exist_ok=True)
    made.write_text(f"steps:\n  - run: {workflow}\n", encoding="utf-8")


def test_the_project_pins_everything():
    assert problems() == []


def test_main_passes_over_the_project():
    assert main() == 0


def test_every_pin_is_read():
    held = pins()
    assert held["click"] == "8.1.8"
    assert held["pytest"] == "8.3.4"


def test_a_name_is_normalised():
    assert "typing-extensions" in pins()


def test_the_declared_dependencies_are_found():
    names = declared()
    assert "click" in names
    assert "hatchling" in names


def test_every_declared_dependency_is_pinned():
    held = pins()
    assert all(name in held for name in declared())


def test_the_transitive_closure_is_pinned_too():
    held = pins()
    for name in ("packaging", "pluggy", "iniconfig", "typing-extensions"):
        assert name in held


def test_a_loose_requirement_is_reported(tmp_path):
    a_project(tmp_path, "click>=8.0\nhatchling==1.27.0\n")
    found = problems(tmp_path)
    assert any("without an exact version" in line for line in found)


def test_a_missing_dependency_is_reported(tmp_path):
    a_project(tmp_path, "hatchling==1.27.0\n")
    found = problems(tmp_path)
    assert any("is a dependency and is not" in line for line in found)


def test_a_file_out_of_order_is_reported(tmp_path):
    a_project(tmp_path, "hatchling==1.27.0\nclick==8.1.8\n")
    found = problems(tmp_path)
    assert any("not in name order" in line for line in found)


def test_a_repeated_name_is_reported(tmp_path):
    a_project(tmp_path, "click==8.1.8\nclick==8.1.9\nhatchling==1.27.0\n")
    found = problems(tmp_path)
    assert any("names something twice" in line for line in found)


def test_an_install_without_the_constraints_is_reported(tmp_path):
    a_project(tmp_path, "click==8.1.8\nhatchling==1.27.0\n", workflow="python -m pip install x")
    found = problems(tmp_path)
    assert any("installs without the constraints file" in line for line in found)


def test_a_missing_workflow_is_reported(tmp_path):
    (tmp_path / CONSTRAINTS).write_text("click==8.1.8\nhatchling==1.27.0\n", encoding="utf-8")
    (tmp_path / PYPROJECT).write_text(
        '[build-system]\nrequires = ["hatchling==1.27.0"]\n'
        '[project]\nname = "x"\ndependencies = ["click==8.1.8"]\n',
        encoding="utf-8",
    )
    found = problems(tmp_path)
    assert any("is not there" in line for line in found)


def test_a_comment_is_skipped(tmp_path):
    a_project(tmp_path, "# a note\nclick==8.1.8\nhatchling==1.27.0\n")
    assert problems(tmp_path) == []


def test_a_clean_project_reports_nothing(tmp_path):
    a_project(tmp_path, "click==8.1.8\nhatchling==1.27.0\n")
    assert problems(tmp_path) == []


@pytest.mark.parametrize("name", ["click", "pytest", "ruff", "mypy", "coverage"])
def test_the_tools_the_build_runs_are_pinned(name):
    assert name in pins()
