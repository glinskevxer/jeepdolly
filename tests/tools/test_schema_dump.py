from jeepdolly.store.migrations import LATEST
from jeepdolly.store.sqlite import MEMORY, opened
from jeepdolly.tools.schema_dump import (
    DOC_NAME,
    Column,
    columns_of,
    doc_path,
    indexes_of,
    main,
    render,
)


def test_the_committed_schema_is_current():
    assert main([]) == 0


def test_the_document_names_every_table():
    text = render()
    for table in ("carrier", "rig", "rig_axle", "node", "segment", "structure", "permit"):
        assert f"## {table}" in text


def test_the_document_lists_the_columns():
    text = render()
    assert "| usdot |" in text
    assert "| posted_gross |" in text


def test_the_document_marks_the_primary_keys():
    assert "primary key" in render()


def test_the_document_marks_not_null():
    assert "not null" in render()


def test_the_document_lists_the_indexes():
    assert "carrier_by_name" in render()


def test_the_document_carries_the_schema_version():
    assert f"Schema version {LATEST}" in render()


def test_the_document_ends_with_one_newline():
    text = render()
    assert text.endswith("\n")
    assert not text.endswith("\n\n")


def test_the_document_sits_under_docs():
    assert doc_path().parent.name == "docs"
    assert doc_path().name == DOC_NAME


def test_columns_of_a_table_that_is_not_there_is_empty():
    with opened(MEMORY) as connection:
        assert columns_of(connection, "nothing") == []


def test_indexes_of_a_table_with_none_is_empty():
    with opened(MEMORY) as connection:
        connection.execute("CREATE TABLE thing (code TEXT PRIMARY KEY)")
        assert indexes_of(connection, "thing") == []


def test_a_column_note_gathers_its_constraints():
    made = Column(name="code", kind="TEXT", not_null=True, default="", primary_key=True)
    assert made.note == "primary key, not null"


def test_a_column_note_shows_a_default():
    made = Column(name="active", kind="INTEGER", not_null=True, default="1", primary_key=False)
    assert "default 1" in made.note


def test_a_plain_column_has_no_note():
    made = Column(name="x", kind="TEXT", not_null=False, default="", primary_key=False)
    assert made.note == ""


def test_writing_puts_it_where_it_belongs(monkeypatch, tmp_path):
    from jeepdolly.tools import schema_dump

    target = tmp_path / "docs" / DOC_NAME
    monkeypatch.setattr(schema_dump, "doc_path", lambda: target)
    assert schema_dump.write() == target
    assert target.read_text() == render()


def test_the_check_fires_on_a_stale_document(monkeypatch, tmp_path, capsys):
    from jeepdolly.tools import schema_dump

    stale = tmp_path / "schema.md"
    stale.write_text("# out of date\n")
    monkeypatch.setattr(schema_dump, "doc_path", lambda: stale)
    assert schema_dump.main([]) == 1
    assert "out of date" in capsys.readouterr().out


def test_the_check_fires_when_it_was_never_written(monkeypatch, tmp_path, capsys):
    from jeepdolly.tools import schema_dump

    monkeypatch.setattr(schema_dump, "doc_path", lambda: tmp_path / "nothing.md")
    assert schema_dump.main([]) == 1
    assert "never been written" in capsys.readouterr().out


def test_writing_reports_where_it_went(monkeypatch, tmp_path, capsys):
    from jeepdolly.tools import schema_dump

    monkeypatch.setattr(schema_dump, "doc_path", lambda: tmp_path / "schema.md")
    assert schema_dump.main(["--write"]) == 0
    assert "wrote" in capsys.readouterr().out
