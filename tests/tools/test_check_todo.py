from jeepdolly.tools.check_todo import MARKERS, SKIP_MARKS, main, problems


def test_the_repository_has_no_markers():
    assert problems() == []


def test_main_passes_over_the_package():
    assert main() == 0


def test_the_marker_list_is_upper_case():
    assert all(word == word.upper() for word in MARKERS)


def test_todo_is_one_of_the_markers():
    assert "TODO" in MARKERS


def test_fixme_is_one_of_the_markers():
    assert "FIXME" in MARKERS


def test_the_skip_marks_cover_both_forms():
    assert "pytest.mark.skip" in SKIP_MARKS
    assert "pytest.mark.xfail" in SKIP_MARKS


def test_the_check_reads_both_trees():
    from jeepdolly.tools.walk import source_files, suite_files

    assert source_files()
    assert suite_files()
