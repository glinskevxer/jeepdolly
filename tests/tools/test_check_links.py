from jeepdolly.tools.check_links import DESIGN, main, problems, referenced


def test_the_design_document_names_nothing_that_is_gone():
    assert problems() == []


def test_main_passes_over_the_design_document():
    assert main() == 0


def test_the_design_document_is_under_docs():
    assert DESIGN.startswith("docs/")


def test_a_module_name_is_picked_out():
    assert referenced("see `rig.dolly` for that") == ["rig.dolly"]


def test_a_dotted_attribute_is_picked_out():
    assert referenced("`rig.spread.spread_score` does it") == ["rig.spread.spread_score"]


def test_a_table_name_is_left_alone():
    assert referenced("the `carrier` table") == []


def test_an_english_phrase_is_left_alone():
    assert referenced("`the office` says so") == []


def test_a_name_from_another_package_is_left_alone():
    assert referenced("`click.testing` is used here") == []


def test_the_same_name_twice_is_listed_once():
    assert referenced("`rig.dolly` and `rig.dolly`") == ["rig.dolly"]


def test_a_dead_reference_is_reported(monkeypatch, tmp_path):
    from jeepdolly.tools import check_links

    fake = tmp_path / "design.md"
    fake.write_text("see `rig.nothing_like_this` for that\n", encoding="utf-8")
    monkeypatch.setattr(check_links, "DESIGN", str(fake))
    monkeypatch.setattr(check_links, "repo_root", lambda: tmp_path.parent)
    found = check_links.problems()
    assert any("nothing_like_this" in line for line in found)


def test_a_missing_design_document_is_reported(monkeypatch, tmp_path):
    from jeepdolly.tools import check_links

    monkeypatch.setattr(check_links, "DESIGN", "docs/nothing-like-this.md")
    found = check_links.problems()
    assert found
    assert "is not there" in found[0]


def test_the_design_document_names_the_desk():
    from jeepdolly.tools.walk import repo_root

    text = (repo_root() / DESIGN).read_text(encoding="utf-8")
    assert "permit.desk" in referenced(text)


def test_the_design_document_names_a_handful_of_modules():
    from jeepdolly.tools.walk import repo_root

    text = (repo_root() / DESIGN).read_text(encoding="utf-8")
    assert len(referenced(text)) >= 5
