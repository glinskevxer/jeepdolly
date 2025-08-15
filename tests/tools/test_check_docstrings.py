from jeepdolly.tools.check_docstrings import EXEMPT, MIN_WORDS, main, problems


def test_the_package_has_no_problems():
    assert problems() == []


def test_main_passes_over_the_package():
    assert main() == 0


def test_the_word_floor_is_a_sentence():
    assert MIN_WORDS >= 3


def test_the_exempt_list_is_only_dunders():
    assert all(name.startswith("__") for name in EXEMPT)


def test_post_init_is_exempt():
    assert "__post_init__" in EXEMPT


def test_the_string_method_is_exempt():
    assert "__str__" in EXEMPT


def test_init_is_not_exempt():
    assert "__init__" not in EXEMPT


def test_the_check_reads_the_whole_package():
    from jeepdolly.tools.walk import source_files

    assert len(source_files()) > 40
