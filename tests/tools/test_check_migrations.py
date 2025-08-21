from jeepdolly.store.migrations import MIGRATIONS, Migration
from jeepdolly.tools.check_migrations import (
    LOCK_NAME,
    fingerprint,
    lock_path,
    main,
    problems,
    read_lock,
)


def test_the_migrations_are_all_fingerprinted():
    assert problems() == []


def test_main_passes_over_the_package():
    assert main([]) == 0


def test_the_lock_file_is_beside_the_migrations():
    assert lock_path().name == LOCK_NAME
    assert lock_path().parent.name == "store"


def test_the_lock_covers_every_migration():
    locked = read_lock()
    assert set(locked) == {m.number for m in MIGRATIONS}


def test_a_fingerprint_is_stable():
    assert fingerprint(MIGRATIONS[0]) == fingerprint(MIGRATIONS[0])


def test_two_migrations_fingerprint_differently():
    assert fingerprint(MIGRATIONS[0]) != fingerprint(MIGRATIONS[1])


def test_reindenting_a_statement_does_not_change_the_fingerprint():
    first = MIGRATIONS[0]
    spaced = Migration(
        number=first.number,
        name=first.name,
        statements=tuple("   " + s.replace("\n", "\n  ") for s in first.statements),
    )
    assert fingerprint(spaced) == fingerprint(first)


def test_changing_a_statement_changes_the_fingerprint():
    first = MIGRATIONS[0]
    changed = Migration(
        number=first.number,
        name=first.name,
        statements=(*first.statements, "CREATE INDEX extra ON carrier (usdot)"),
    )
    assert fingerprint(changed) != fingerprint(first)


def test_renaming_a_migration_changes_the_fingerprint():
    first = MIGRATIONS[0]
    renamed = Migration(number=first.number, name="other", statements=first.statements)
    assert fingerprint(renamed) != fingerprint(first)


def test_a_fingerprint_is_short_enough_to_read():
    assert len(fingerprint(MIGRATIONS[0])) == 16


def test_the_check_fires_when_a_migration_moves(monkeypatch, tmp_path):
    from jeepdolly.tools import check_migrations

    fake = tmp_path / "migrations.lock"
    fake.write_text("1 0000000000000000\n")
    monkeypatch.setattr(check_migrations, "lock_path", lambda: fake)
    found = check_migrations.problems()
    assert any("has been edited" in line for line in found)


def test_the_check_fires_on_a_missing_fingerprint(monkeypatch, tmp_path):
    from jeepdolly.tools import check_migrations

    fake = tmp_path / "migrations.lock"
    fake.write_text("")
    monkeypatch.setattr(check_migrations, "lock_path", lambda: fake)
    found = check_migrations.problems()
    assert any("no fingerprint" in line for line in found)


def test_the_check_fires_on_a_migration_that_was_removed(monkeypatch, tmp_path):
    from jeepdolly.tools import check_migrations

    fake = tmp_path / "migrations.lock"
    lines = [f"{m.number} {fingerprint(m)}" for m in MIGRATIONS]
    lines.append("99 0000000000000000")
    fake.write_text("\n".join(lines) + "\n")
    monkeypatch.setattr(check_migrations, "lock_path", lambda: fake)
    assert any("no longer in the list" in line for line in check_migrations.problems())


def test_update_rewrites_the_lock(monkeypatch, tmp_path, capsys):
    from jeepdolly.tools import check_migrations

    fake = tmp_path / "migrations.lock"
    monkeypatch.setattr(check_migrations, "lock_path", lambda: fake)
    assert check_migrations.main(["--update"]) == 0
    assert fake.exists()
    assert "wrote" in capsys.readouterr().out


def test_a_missing_lock_reads_as_empty(monkeypatch, tmp_path):
    from jeepdolly.tools import check_migrations

    monkeypatch.setattr(check_migrations, "lock_path", lambda: tmp_path / "nothing.lock")
    assert check_migrations.read_lock() == {}


def test_comments_in_the_lock_are_skipped(monkeypatch, tmp_path):
    from jeepdolly.tools import check_migrations

    fake = tmp_path / "migrations.lock"
    fake.write_text("# a comment\n\n1 abc\n")
    monkeypatch.setattr(check_migrations, "lock_path", lambda: fake)
    assert check_migrations.read_lock() == {1: "abc"}
