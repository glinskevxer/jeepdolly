import pytest

from jeepdolly.errors import BadValueError
from jeepdolly.tools.document import Document


def a_document(tmp_path, text: str = "hello\n") -> Document:
    """A document writing to a temporary file."""
    return Document(
        name="pretend",
        render=lambda: text,
        path_of=lambda: tmp_path / "docs" / "pretend.md",
    )


def test_a_document_refuses_an_empty_name(tmp_path):
    with pytest.raises(BadValueError):
        Document(name="  ", render=lambda: "x", path_of=lambda: tmp_path / "x.md")


def test_a_new_document_has_never_been_written(tmp_path):
    assert not a_document(tmp_path).written


def test_a_new_document_is_not_current(tmp_path):
    assert not a_document(tmp_path).current


def test_writing_makes_the_directory(tmp_path):
    made = a_document(tmp_path)
    assert made.write().parent.name == "docs"


def test_a_written_document_is_current(tmp_path):
    made = a_document(tmp_path)
    made.write()
    assert made.current


def test_the_text_comes_from_the_renderer(tmp_path):
    assert a_document(tmp_path, "goodbye\n").text == "goodbye\n"


def test_main_writes_when_told_to(tmp_path, capsys):
    made = a_document(tmp_path)
    assert made.main(["--write"]) == 0
    assert "wrote" in capsys.readouterr().out


def test_main_passes_on_a_current_document(tmp_path):
    made = a_document(tmp_path)
    made.write()
    assert made.main([]) == 0


def test_main_fails_when_it_was_never_written(tmp_path, capsys):
    assert a_document(tmp_path).main([]) == 1
    assert "never been written" in capsys.readouterr().out


def test_main_fails_on_a_stale_document(tmp_path, capsys):
    made = a_document(tmp_path)
    made.write()
    stale = Document(name="pretend", render=lambda: "changed\n", path_of=made.path_of)
    assert stale.main([]) == 1
    assert "out of date" in capsys.readouterr().out


def test_the_path_is_read_at_the_time_it_is_asked_for(tmp_path):
    where = {"at": tmp_path / "first.md"}
    made = Document(name="pretend", render=lambda: "x", path_of=lambda: where["at"])
    assert made.path.name == "first.md"
    where["at"] = tmp_path / "second.md"
    assert made.path.name == "second.md"
