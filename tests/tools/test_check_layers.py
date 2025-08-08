import pytest

from jeepdolly.tools.check_layers import LAYERS, layer_of, main, violations


def test_the_package_has_no_violations():
    assert violations() == []


def test_main_passes():
    assert main() == 0


def test_a_leaf_module_takes_its_package_layer():
    assert layer_of("jeepdolly.units.money") == LAYERS["jeepdolly.units"]


def test_the_most_specific_prefix_wins():
    assert layer_of("jeepdolly.limits.finding") == 2
    assert layer_of("jeepdolly.limits.statute") == 4


def test_a_module_outside_the_package_has_no_layer():
    assert layer_of("sqlite3") is None
    assert layer_of("click") is None


def test_the_package_itself_sits_at_the_bottom():
    assert layer_of("jeepdolly") == 0


def test_a_module_we_do_not_know_has_no_layer():
    assert layer_of("jeepdolly.nothing_like_this") is None


def test_the_layers_climb_from_units_to_the_command_line():
    assert LAYERS["jeepdolly.units"] < LAYERS["jeepdolly.cli"]


def test_the_store_sits_above_everything_it_reads():
    for lower in ("jeepdolly.permit.permit", "jeepdolly.billing", "jeepdolly.travel"):
        assert LAYERS[lower] < LAYERS["jeepdolly.store"]


def test_the_desk_sits_above_the_store():
    assert LAYERS["jeepdolly.store"] < LAYERS["jeepdolly.permit.desk"]


def test_the_check_fires_when_a_layer_is_moved(monkeypatch):
    monkeypatch.setitem(LAYERS, "jeepdolly.units", 99)
    found = violations()
    assert found
    assert any("jeepdolly.units" in line for line in found)


def test_main_fails_when_the_check_fires(monkeypatch, capsys):
    monkeypatch.setitem(LAYERS, "jeepdolly.units", 99)
    assert main() == 1
    assert "reach up a layer" in capsys.readouterr().out


def test_every_package_of_the_source_tree_is_claimed():
    from jeepdolly.tools.walk import module_of, source_files

    for path in source_files():
        assert layer_of(module_of(path)) is not None, path


@pytest.mark.parametrize("prefix", sorted(LAYERS))
def test_every_claimed_prefix_starts_with_the_package(prefix):
    assert prefix.startswith("jeepdolly.")
