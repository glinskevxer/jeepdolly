import ast

from jeepdolly.tools.check_boundaries import BOUNDARIES, Boundary, calls_in, main, problems


def tree_of(text: str) -> ast.Module:
    """Parse a snippet the way the check does."""
    return ast.parse(text)


def test_the_package_has_no_problems():
    assert problems() == []


def test_main_passes():
    assert main() == 0


def test_calls_in_finds_a_plain_call():
    assert [name for _, name in calls_in(tree_of("go()"))] == ["go"]


def test_calls_in_reads_a_dotted_call():
    assert [name for _, name in calls_in(tree_of("sqlite3.connect(path)"))] == [
        "sqlite3.connect"
    ]


def test_calls_in_reads_a_deeply_dotted_call():
    names = [name for _, name in calls_in(tree_of("a.b.c()"))]
    assert "a.b.c" in names


def test_calls_in_reports_the_line():
    assert calls_in(tree_of("\ngo()"))[0][0] == 2


def test_a_boundary_permits_its_own_module():
    boundary = Boundary(call="print", allowed=("jeepdolly.tools",), because="x")
    assert boundary.permits("jeepdolly.tools")
    assert boundary.permits("jeepdolly.tools.check_sql")


def test_a_boundary_refuses_another_module():
    boundary = Boundary(call="print", allowed=("jeepdolly.tools",), because="x")
    assert not boundary.permits("jeepdolly.store")


def test_a_boundary_does_not_match_a_prefix_by_accident():
    boundary = Boundary(call="print", allowed=("jeepdolly.tool",), because="x")
    assert not boundary.permits("jeepdolly.tools")


def test_connect_is_pinned_to_the_sqlite_module():
    found = next(b for b in BOUNDARIES if b.call == "sqlite3.connect")
    assert found.allowed == ("jeepdolly.store.sqlite",)


def test_the_clock_is_pinned_to_the_command_line():
    found = next(b for b in BOUNDARIES if b.call == "datetime.now")
    assert found.allowed == ("jeepdolly.cli",)


def test_every_boundary_says_why():
    assert all(len(b.because.split()) >= 5 for b in BOUNDARIES)


def test_every_boundary_allows_somebody():
    assert all(b.allowed for b in BOUNDARIES)
