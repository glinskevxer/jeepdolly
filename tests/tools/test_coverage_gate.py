import pytest

from jeepdolly.tools.coverage_gate import FileCoverage, main, report


def a_file(percent: float, name: str = "src/jeepdolly/thing.py") -> FileCoverage:
    """One file's coverage, with the numbers made to match the percentage."""
    total = 100
    covered = int(round(percent))
    return FileCoverage(percent=percent, name=name, covered=covered, total=total)


def test_a_file_counts_what_is_missing():
    assert a_file(90.0).missing == 10


def test_a_file_prints_its_percentage():
    assert "90.0%" in str(a_file(90.0))


def test_a_file_prints_what_is_missing():
    assert "10 missing" in str(a_file(90.0))


def test_files_sort_worst_first():
    files = sorted([a_file(99.0, "b.py"), a_file(50.0, "a.py")])
    assert files[0].name == "a.py"


def test_a_clean_report_passes():
    status, lines = report([a_file(99.0)], floor=96.0, file_floor=85.0, worst=5)
    assert status == 0
    assert "coverage 99.00%" in lines[0]


def test_the_total_floor_fails_the_build():
    status, lines = report([a_file(50.0)], floor=96.0, file_floor=10.0, worst=5)
    assert status == 1
    assert any("under the 96.0% floor" in line for line in lines)


def test_the_file_floor_fails_the_build():
    files = [a_file(99.0, "a.py")] * 20 + [a_file(40.0, "b.py")]
    status, lines = report(files, floor=90.0, file_floor=85.0, worst=5)
    assert status == 1
    assert any("b.py" in line and "file floor" in line for line in lines)


def test_a_high_total_does_not_hide_a_low_file():
    files = [a_file(100.0, f"a{i}.py") for i in range(50)] + [a_file(10.0, "bad.py")]
    status, _ = report(files, floor=90.0, file_floor=85.0, worst=5)
    assert status == 1


def test_the_report_shows_the_worst_few():
    files = sorted([a_file(float(p), f"f{p}.py") for p in (10, 20, 30, 40, 50, 60)])
    _, lines = report(files, floor=0.0, file_floor=0.0, worst=3)
    shown = [line for line in lines if line.startswith("  ")]
    assert len(shown) == 3
    assert "f10.py" in shown[0]


def test_an_empty_report_is_a_hundred_percent():
    status, lines = report([], floor=96.0, file_floor=85.0, worst=5)
    assert status == 0
    assert "100.00%" in lines[0]


def test_the_total_is_weighted_by_size():
    small = FileCoverage(percent=0.0, name="a.py", covered=0, total=1)
    big = FileCoverage(percent=100.0, name="b.py", covered=99, total=99)
    _, lines = report(sorted([small, big]), floor=0.0, file_floor=0.0, worst=1)
    assert "99.00%" in lines[0]


def test_main_reads_a_data_file(tmp_path, capsys):
    with pytest.raises(SystemExit) as caught:
        main(["--help"])
    assert caught.value.code == 0
    assert "coverage" in capsys.readouterr().out


def test_main_on_an_empty_data_file_passes(tmp_path, capsys):
    empty = tmp_path / ".coverage"
    empty.write_bytes(b"")
    assert main(["--data", str(empty), "--floor", "0", "--file-floor", "0"]) == 0
    assert "coverage" in capsys.readouterr().out
