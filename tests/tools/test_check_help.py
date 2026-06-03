import click

from jeepdolly.cli.main import main as cli
from jeepdolly.tools.check_help import MAX_LINE, faults, main, problems, walk_commands


def a_command(help_text: str, option_help: str = "What it is for.") -> click.Command:
    """One command with a help string and one option."""

    @click.command(help=help_text)
    @click.option("--thing", help=option_help)
    def made(thing: str) -> None:
        pass

    return made


def test_every_command_says_what_it_is_for():
    assert problems() == []


def test_main_passes_over_the_command_line():
    assert main() == 0


def test_the_walk_reaches_the_groups_and_their_commands():
    names = [name for name, _ in walk_commands(cli)]
    assert "permit" in names
    assert "permit issue" in names


def test_a_group_is_walked_as_well_as_its_commands():
    found = dict(walk_commands(cli))
    assert isinstance(found["permit"], click.Group)


def test_a_command_with_no_help_is_named():
    assert any("says nothing" in line for line in faults("x", a_command("")))


def test_a_help_string_starting_lower_case_is_named():
    found = faults("x", a_command("do the thing."))
    assert any("starts lower case" in line for line in found)


def test_a_help_string_with_no_full_stop_is_named():
    found = faults("x", a_command("Do the thing"))
    assert any("does not end in a full stop" in line for line in found)


def test_a_help_string_that_is_too_long_is_named():
    found = faults("x", a_command("D" + "o" * MAX_LINE + "."))
    assert any(f"over {MAX_LINE}" in line for line in found)


def test_only_the_first_line_of_a_long_help_is_checked():
    made = a_command("Do the thing.\n\nAnd here is a much longer paragraph about it.")
    assert faults("x", made) == []


def test_an_option_with_no_help_is_named():
    found = faults("x", a_command("Do the thing.", option_help=""))
    assert any("--thing" in line for line in found)


def test_an_option_help_that_is_not_a_sentence_is_named():
    found = faults("x", a_command("Do the thing.", option_help="what it is for"))
    assert any("--thing" in line and "lower case" in line for line in found)


def test_a_good_command_reports_nothing():
    assert faults("x", a_command("Do the thing.")) == []


def test_the_help_option_itself_is_not_checked():
    made = a_command("Do the thing.")
    assert not any("--help" in line for line in faults("x", made))


def test_the_top_level_group_says_what_it_is_for():
    assert cli.help
    assert cli.help.strip().endswith(".")


def test_every_group_says_what_it_is_for():
    for _, command in walk_commands(cli):
        if isinstance(command, click.Group):
            assert command.help


def test_the_line_cap_fits_a_narrow_terminal():
    assert MAX_LINE <= 80
