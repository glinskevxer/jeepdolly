from jeepdolly import __version__
from jeepdolly.cli.main import main
from jeepdolly.store.migrations import LATEST


def test_help_lists_the_groups(runner):
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "carrier" in result.output


def test_version_prints_the_package_version(runner):
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_init_creates_the_file(runner, tmp_path):
    path = tmp_path / "office.sqlite3"
    result = runner.invoke(main, ["-f", str(path), "init"])
    assert result.exit_code == 0
    assert path.exists()
    assert str(LATEST) in result.output


def test_init_refuses_an_existing_file(runner, office_file):
    result = runner.invoke(main, ["-f", str(office_file), "init"])
    assert result.exit_code == 1
    assert "already exists" in result.output


def test_init_with_debug_raises_instead(runner, office_file):
    result = runner.invoke(main, ["-f", str(office_file), "--debug", "init"])
    assert result.exit_code == 1
    assert result.exception is not None


def test_status_on_a_new_file(run):
    result = run("status")
    assert result.exit_code == 0
    assert "carriers 0" in result.output
    assert f"schema {LATEST} of {LATEST}" in result.output


def test_status_on_a_missing_file(runner, tmp_path):
    result = runner.invoke(main, ["-f", str(tmp_path / "nothing.sqlite3"), "status"])
    assert result.exit_code == 1
    assert "no office file" in result.output


def test_the_file_option_reads_the_environment(runner, office_file, monkeypatch):
    monkeypatch.setenv("JEEPDOLLY_FILE", str(office_file))
    result = runner.invoke(main, ["status"])
    assert result.exit_code == 0
