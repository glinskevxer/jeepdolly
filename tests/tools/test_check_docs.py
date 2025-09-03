from jeepdolly.tools.check_docs import WRITERS, main


def test_every_generated_document_is_current():
    assert main() == 0


def test_the_command_reference_is_one_of_them():
    assert "commands" in WRITERS


def test_the_schema_document_is_one_of_them():
    assert "schema" in WRITERS


def test_every_writer_is_callable():
    assert all(callable(writer) for writer in WRITERS.values())


def test_the_check_fires_when_a_writer_says_stale(monkeypatch, capsys):
    from jeepdolly.tools import check_docs

    def always_stale(args: list[str]) -> int:
        """A writer that says its document is out of date."""
        assert args == []
        return 1

    monkeypatch.setitem(check_docs.WRITERS, "pretend", always_stale)
    assert check_docs.main() == 1
    assert "pretend is out of date" in capsys.readouterr().out
