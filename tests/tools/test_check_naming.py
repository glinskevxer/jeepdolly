from jeepdolly.tools.check_naming import MIN_WORDS, VAGUE, main, problems


def test_the_suite_has_no_problems():
    assert problems() == []


def test_main_passes_over_the_suite():
    assert main() == 0


def test_the_word_floor_is_four():
    assert MIN_WORDS == 4


def test_the_domains_own_words_are_not_listed():
    for word in ("good", "other", "case"):
        assert word not in VAGUE


def test_a_word_that_says_nothing_is_listed():
    assert "works" in VAGUE


def test_the_vague_list_is_all_lower_case():
    assert all(word == word.lower() for word in VAGUE)


def test_the_vague_list_holds_no_domain_words():
    for word in ("axle", "bridge", "permit", "carrier", "escort"):
        assert word not in VAGUE


def test_the_suite_is_big_enough_to_be_worth_checking():
    from jeepdolly.tools.walk import suite_files

    assert len(suite_files()) > 20
