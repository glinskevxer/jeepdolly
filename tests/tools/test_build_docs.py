import click

from jeepdolly.tools.build_docs import DOC_NAME, doc_path, main, render, write


def test_the_committed_reference_is_current():
    assert main([]) == 0


def test_the_reference_names_every_group():
    text = render()
    for group in ("carrier", "road", "rig", "permit", "account", "report"):
        assert f"### `jeepdolly {group}`" in text


def test_the_reference_reaches_the_subcommands():
    text = render()
    assert "### `jeepdolly permit issue`" in text
    assert "### `jeepdolly road structure`" in text


def test_the_reference_lists_the_options():
    text = render()
    assert "`--carrier`" in text
    assert "required option" in text


def test_the_reference_marks_the_flags():
    assert "| flag |" in render()


def test_the_reference_names_the_arguments():
    text = render()
    assert "| argument |" in text


def test_the_reference_carries_the_version():
    from jeepdolly import __version__

    assert __version__ in render()


def test_the_reference_ends_with_one_newline():
    text = render()
    assert text.endswith("\n")
    assert not text.endswith("\n\n")


def test_the_document_sits_under_docs():
    assert doc_path().parent.name == "docs"
    assert doc_path().name == DOC_NAME


def test_writing_puts_it_where_it_belongs(monkeypatch, tmp_path):
    from jeepdolly.tools import build_docs

    target = tmp_path / "docs" / DOC_NAME
    monkeypatch.setattr(build_docs, "doc_path", lambda: target)
    assert build_docs.write() == target
    assert target.read_text() == render()


def test_the_check_fires_on_a_stale_document(monkeypatch, tmp_path, capsys):
    from jeepdolly.tools import build_docs

    stale = tmp_path / "commands.md"
    stale.write_text("# out of date\n")
    monkeypatch.setattr(build_docs, "doc_path", lambda: stale)
    assert build_docs.main([]) == 1
    assert "out of date" in capsys.readouterr().out


def test_the_check_fires_when_it_was_never_written(monkeypatch, tmp_path, capsys):
    from jeepdolly.tools import build_docs

    monkeypatch.setattr(build_docs, "doc_path", lambda: tmp_path / "nothing.md")
    assert build_docs.main([]) == 1
    assert "never been written" in capsys.readouterr().out


def test_writing_reports_where_it_went(monkeypatch, tmp_path, capsys):
    from jeepdolly.tools import build_docs

    monkeypatch.setattr(build_docs, "doc_path", lambda: tmp_path / "commands.md")
    assert build_docs.main(["--write"]) == 0
    assert "wrote" in capsys.readouterr().out


def test_the_command_tree_is_a_group():
    from jeepdolly.cli.main import main as cli

    assert isinstance(cli, click.Group)


def test_the_writer_is_a_callable_the_build_can_reach():
    assert callable(write)


def test_the_document_knows_its_own_name():
    from jeepdolly.tools.build_docs import DOCUMENT

    assert DOCUMENT.name == "build_docs"


def test_the_document_is_current():
    from jeepdolly.tools.build_docs import DOCUMENT

    assert DOCUMENT.current
