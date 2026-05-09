from jeepdolly.tools.check_readme import README, main, problems, resolves, shown


def test_every_example_in_the_readme_runs():
    assert problems() == []


def test_main_passes_over_the_readme():
    assert main() == 0


def test_an_indented_command_is_picked_out():
    assert shown("    jeepdolly init permits.sqlite3\n") == [("init", "permits.sqlite3")]


def test_a_line_stops_at_its_first_option():
    text = "    jeepdolly permit apply --carrier VANCE --rig R-00001\n"
    assert shown(text) == [("permit", "apply")]


def test_a_continuation_backslash_ends_the_line():
    assert shown("    jeepdolly carrier add \\\n") == [("carrier", "add")]


def test_prose_is_left_alone():
    assert shown("The jeepdolly command does things.\n") == []


def test_an_unindented_line_is_left_alone():
    assert shown("jeepdolly init permits.sqlite3\n") == []


def test_the_same_command_twice_is_listed_once():
    text = "    jeepdolly status\n    jeepdolly status\n"
    assert shown(text) == [("status",)]


def test_a_top_level_command_resolves():
    assert resolves(("init",))


def test_a_subcommand_of_a_group_resolves():
    assert resolves(("permit", "issue"))


def test_a_command_with_arguments_after_it_resolves():
    assert resolves(("permit", "issue", "1"))


def test_a_group_on_its_own_does_not_resolve():
    assert not resolves(("permit",))


def test_a_name_that_is_not_a_command_does_not_resolve():
    assert not resolves(("permit", "issued", "1"))


def test_nothing_at_all_does_not_resolve():
    assert not resolves(())


def test_a_dead_example_is_reported(monkeypatch, tmp_path):
    from jeepdolly.tools import check_readme

    fake = tmp_path / "README.md"
    fake.write_text("    jeepdolly permit nothing-like-this\n", encoding="utf-8")
    monkeypatch.setattr(check_readme, "README", fake.name)
    monkeypatch.setattr(check_readme, "repo_root", lambda: tmp_path)
    found = check_readme.problems()
    assert any("nothing-like-this" in line for line in found)


def test_a_missing_readme_is_reported(monkeypatch, tmp_path):
    from jeepdolly.tools import check_readme

    monkeypatch.setattr(check_readme, "README", "nothing-like-this.md")
    found = check_readme.problems()
    assert found
    assert "is not there" in found[0]


def test_the_readme_shows_a_handful_of_commands():
    from jeepdolly.tools.walk import repo_root

    text = (repo_root() / README).read_text(encoding="utf-8")
    assert len(shown(text)) >= 6
