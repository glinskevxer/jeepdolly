from jeepdolly.tools.build_glossary import (
    DOC_NAME,
    EXTRA,
    Term,
    doc_path,
    enum_terms,
    main,
    render,
)


def test_the_committed_glossary_is_current():
    assert main([]) == 0


def test_the_glossary_holds_the_severities():
    words = {term.word for term in enum_terms()}
    assert {"note", "permit", "refuse"} <= words


def test_the_glossary_holds_the_structure_kinds():
    words = {term.word for term in enum_terms()}
    assert {"bridge", "culvert", "overhead", "tunnel"} <= words


def test_the_glossary_holds_the_hitch_kinds():
    words = {term.word for term in enum_terms()}
    assert {"jeep", "booster"} <= words


def test_the_glossary_holds_the_account_entry_kinds():
    words = {term.word for term in enum_terms()}
    assert {"deposit", "charge", "refund", "adjustment"} <= words


def test_every_term_says_where_it_is_declared():
    assert all(term.where.startswith("jeepdolly.") for term in enum_terms())


def test_every_term_carries_a_sense():
    assert all(term.sense for term in enum_terms())


def test_the_terms_come_out_sorted():
    words = [term.word for term in enum_terms()]
    assert words == sorted(words)


def test_the_ideas_are_in_the_document():
    text = render()
    for word, _ in EXTRA:
        assert f"| {word} |" in text


def test_the_jeep_dolly_itself_is_explained():
    assert "jeep dolly" in dict(EXTRA)


def test_every_idea_is_a_sentence():
    assert all(len(sense.split()) >= 8 for _, sense in EXTRA)


def test_a_term_prints_where_it_came_from():
    made = Term(word="jeep", sense="an axle set", where="jeepdolly.rig.dolly.Hitch")
    assert str(made) == "jeep (jeepdolly.rig.dolly.Hitch): an axle set"


def test_a_term_without_a_place_prints_plainly():
    assert str(Term(word="jeep", sense="an axle set")) == "jeep: an axle set"


def test_the_document_sits_under_docs():
    assert doc_path().parent.name == "docs"
    assert doc_path().name == DOC_NAME


def test_the_check_fires_on_a_stale_document(monkeypatch, tmp_path, capsys):
    from jeepdolly.tools import build_glossary

    stale = tmp_path / "glossary.md"
    stale.write_text("# out of date\n")
    monkeypatch.setattr(build_glossary, "doc_path", lambda: stale)
    assert build_glossary.main([]) == 1
    assert "out of date" in capsys.readouterr().out


def test_the_check_fires_when_it_was_never_written(monkeypatch, tmp_path, capsys):
    from jeepdolly.tools import build_glossary

    monkeypatch.setattr(build_glossary, "doc_path", lambda: tmp_path / "nothing.md")
    assert build_glossary.main([]) == 1
    assert "never been written" in capsys.readouterr().out


def test_writing_reports_where_it_went(monkeypatch, tmp_path, capsys):
    from jeepdolly.tools import build_glossary

    monkeypatch.setattr(build_glossary, "doc_path", lambda: tmp_path / "glossary.md")
    assert build_glossary.main(["--write"]) == 0
    assert "wrote" in capsys.readouterr().out
