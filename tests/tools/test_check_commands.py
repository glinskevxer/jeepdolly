import click
import pytest

from jeepdolly.cli.main import main as cli
from jeepdolly.tools.check_commands import (
    SUITE,
    invocation,
    main,
    paths_of,
    problems,
    untested,
)


def test_every_command_is_reached_by_the_suite():
    assert problems() == []


def test_main_passes_over_the_command_line():
    assert main() == 0


def test_the_paths_reach_into_the_groups():
    found = paths_of(cli)
    assert ("permit", "issue") in found
    assert ("road", "structure") in found
    assert ("account", "statement") in found


def test_a_top_level_command_is_one_word():
    assert ("init",) in paths_of(cli)


def test_a_group_itself_is_not_a_path():
    found = paths_of(cli)
    assert ("permit",) not in found


def test_the_paths_come_out_sorted():
    found = [" ".join(path) for path in paths_of(cli)]
    assert found == sorted(found)


def test_every_path_is_a_real_command():
    for path in paths_of(cli):
        node: click.Command = cli
        for word in path:
            assert isinstance(node, click.Group)
            node = node.commands[word]
        assert not isinstance(node, click.Group)


def test_the_pattern_matches_a_plain_invocation():
    assert invocation(("permit", "issue")).search('run("permit", "issue", "1")')


def test_the_pattern_matches_one_split_over_lines():
    text = 'run(\n    "permit",\n    "issue",\n    "1",\n)'
    assert invocation(("permit", "issue")).search(text)


def test_the_pattern_does_not_match_the_words_apart():
    assert invocation(("permit", "issue")).search('run("permit", "void")') is None


def test_the_pattern_does_not_match_a_bare_name():
    assert invocation(("permit", "issue")).search("the word issue appears here") is None


def test_untested_finds_a_command_nothing_invokes():
    paths = [("permit", "issue"), ("permit", "nothing")]
    assert untested('run("permit", "issue")', paths) == [("permit", "nothing")]


def test_untested_is_empty_when_everything_is_invoked():
    paths = [("permit", "issue")]
    assert untested('run("permit", "issue")', paths) == []


def test_the_suite_directory_is_where_the_command_tests_live():
    from jeepdolly.tools.walk import repo_root

    assert (repo_root() / SUITE).is_dir()


def test_the_check_fires_when_the_suite_is_gone(monkeypatch):
    from jeepdolly.tools import check_commands

    monkeypatch.setattr(check_commands, "SUITE", "tests/nothing-like-this")
    found = check_commands.problems()
    assert found
    assert "is not there" in found[0]


def test_there_are_enough_commands_to_be_worth_checking():
    assert len(paths_of(cli)) > 25


@pytest.mark.parametrize("group", ["carrier", "road", "rig", "permit", "account", "report"])
def test_every_group_has_commands(group):
    node = cli.commands[group]
    assert isinstance(node, click.Group)
    assert node.commands


def test_the_walk_script_runs_every_command():
    from jeepdolly.tools.check_commands import WALK, unwalked
    from jeepdolly.tools.walk import repo_root

    text = (repo_root() / WALK).read_text(encoding="utf-8")
    assert unwalked(text, paths_of(cli)) == []


def test_the_spoken_pattern_matches_a_run_line():
    from jeepdolly.tools.check_commands import spoken

    assert spoken(("permit", "issue")).search("run permit issue 1 --on 2025-06-17")


def test_the_spoken_pattern_matches_an_indented_line():
    from jeepdolly.tools.check_commands import spoken

    assert spoken(("permit", "issue")).search("  run permit issue 1\n")


def test_the_spoken_pattern_does_not_match_a_prefix():
    from jeepdolly.tools.check_commands import spoken

    assert spoken(("permit", "issue")).search("run permit issued 1") is None


def test_the_spoken_pattern_needs_the_run_wrapper():
    from jeepdolly.tools.check_commands import spoken

    assert spoken(("permit", "issue")).search("jeepdolly permit issue 1") is None


def test_unwalked_finds_a_command_the_script_misses():
    from jeepdolly.tools.check_commands import unwalked

    paths = [("permit", "issue"), ("permit", "nothing")]
    assert unwalked("run permit issue 1", paths) == [("permit", "nothing")]


def test_a_missing_walk_script_is_reported(monkeypatch):
    from jeepdolly.tools import check_commands

    monkeypatch.setattr(check_commands, "WALK", "scripts/nothing-like-this.sh")
    found = check_commands.problems()
    assert any("nothing drives an installed copy" in line for line in found)


def test_the_walk_script_is_where_it_is_said_to_be():
    from jeepdolly.tools.check_commands import WALK
    from jeepdolly.tools.walk import repo_root

    assert (repo_root() / WALK).exists()
