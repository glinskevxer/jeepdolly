from tests.cli.test_permit import apply_one


def test_the_first_application_warns_about_nothing(stocked):
    result = apply_one(stocked)
    assert result.exit_code == 0
    assert "warning" not in result.output


def test_the_same_application_twice_warns(stocked):
    apply_one(stocked)
    result = apply_one(stocked)
    assert "warning" in result.output
    assert "the same move" in result.output


def test_a_different_carriers_move_does_not_warn(stocked):
    apply_one(stocked)
    stocked(
        "carrier",
        "add",
        "--code",
        "SUMMIT",
        "--name",
        "Summit Rigging",
        "--usdot",
        "2277431",
        "--state",
        "ID",
    )
    stocked("rig", "build", "--carrier", "SUMMIT", "--name", "3S2")
    result = apply_one(stocked, **{"--carrier": "SUMMIT", "--rig": "R-00002"})
    assert "warning" not in result.output


def test_a_move_on_other_days_does_not_warn(stocked):
    apply_one(stocked)
    result = apply_one(stocked, **{"--first": "2025-07-10", "--last": "2025-07-12"})
    assert "warning" not in result.output


def test_a_move_to_somewhere_else_does_not_warn(stocked):
    apply_one(stocked)
    result = apply_one(stocked, **{"--destination": "JCT-C"})
    assert "warning" not in result.output


def test_a_heavier_load_warns_less_certainly(stocked):
    apply_one(stocked)
    result = apply_one(stocked, **{"--weight": "160,000"})
    assert "probably the same move" in result.output


def test_a_lone_application_looks_like_nothing(stocked):
    apply_one(stocked)
    assert "does not look like anything" in stocked("permit", "alike", "1").output


def test_a_repeated_application_is_listed(stocked):
    apply_one(stocked)
    apply_one(stocked)
    assert "application 1" in stocked("permit", "alike", "2").output


def test_asking_about_an_unknown_application_fails(stocked):
    assert stocked("permit", "alike", "99").exit_code != 0


def test_the_listing_leaves_the_application_itself_out(stocked):
    apply_one(stocked)
    apply_one(stocked)
    assert "application 2" not in stocked("permit", "alike", "2").output
