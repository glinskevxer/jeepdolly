import datetime as dt

import pytest

from jeepdolly.errors import BadValueError, NotAllowedError
from jeepdolly.permit.review import (
    CLOSED,
    MAX_CONDITIONS,
    MAX_ENGINEER,
    Review,
    ReviewState,
    open_review,
)

OPENED = dt.date(2025, 7, 1)
DECIDED = dt.date(2025, 7, 10)


def a_review(**over: object) -> Review:
    """An open review, with any part of it swapped out."""
    kw: dict[str, object] = {
        "reference": "E-00001",
        "application_key": 3,
        "opened_on": OPENED,
    }
    kw.update(over)
    return Review(**kw)  # type: ignore[arg-type]


def test_a_new_review_is_open():
    made = open_review("E-00001", 3, OPENED)  # type: ignore[arg-type]
    assert made.open
    assert made.state is ReviewState.OPEN


def test_a_new_review_names_no_engineer():
    assert open_review("E-00001", 3, OPENED).engineer == ""  # type: ignore[arg-type]


def test_a_review_normalises_its_reference():
    assert a_review(reference="e-00001").reference == "E-00001"


def test_a_review_refuses_an_application_key_of_zero():
    with pytest.raises(BadValueError):
        a_review(application_key=0)


def test_a_review_refuses_a_bool_application_key():
    with pytest.raises(BadValueError):
        a_review(application_key=True)


def test_a_review_refuses_a_datetime_opening():
    with pytest.raises(BadValueError):
        a_review(opened_on=dt.datetime(2025, 7, 1, tzinfo=dt.UTC))


def test_an_open_review_refuses_an_engineer():
    with pytest.raises(BadValueError):
        a_review(engineer="R Halloran")


def test_an_open_review_refuses_a_decision_day():
    with pytest.raises(BadValueError):
        a_review(decided_on=DECIDED)


def test_approving_records_the_engineer():
    made = a_review().approved_by("R Halloran", DECIDED)
    assert made.engineer == "R Halloran"
    assert made.approved


def test_approving_records_the_conditions():
    made = a_review().approved_by("R Halloran", DECIDED, ("walking pace over the bridge",))
    assert made.conditions == ("walking pace over the bridge",)


def test_approving_collapses_whitespace_in_a_condition():
    made = a_review().approved_by("R Halloran", DECIDED, ("walking   pace",))
    assert made.conditions == ("walking pace",)


def test_approving_closes_the_review():
    assert not a_review().approved_by("R Halloran", DECIDED).open


def test_a_review_counts_the_days_it_took():
    assert a_review().approved_by("R Halloran", DECIDED).days_open == 9


def test_an_open_review_has_taken_no_days_yet():
    assert a_review().days_open == 0


def test_refusing_records_the_reason():
    made = a_review().refused_by(
        "R Halloran", DECIDED, "the Clark Fork bridge will not take it"
    )
    assert made.state is ReviewState.REFUSED
    assert "Clark Fork" in made.note


def test_refusing_needs_a_reason():
    with pytest.raises(BadValueError):
        a_review().refused_by("R Halloran", DECIDED, "  ")


def test_refusing_may_not_carry_conditions():
    with pytest.raises(BadValueError):
        a_review(
            state=ReviewState.REFUSED,
            engineer="R Halloran",
            decided_on=DECIDED,
            note="no",
            conditions=("walking pace",),
        )


def test_withdrawing_names_no_engineer():
    made = a_review().withdrawn(DECIDED)
    assert made.state is ReviewState.WITHDRAWN
    assert made.engineer == ""


def test_withdrawing_carries_a_default_note():
    assert "carrier" in a_review().withdrawn(DECIDED).note


def test_withdrawing_takes_a_note_of_its_own():
    assert a_review().withdrawn(DECIDED, "load cancelled").note == "load cancelled"


def test_a_withdrawal_refuses_an_engineer():
    with pytest.raises(BadValueError):
        a_review(
            state=ReviewState.WITHDRAWN,
            engineer="R Halloran",
            decided_on=DECIDED,
        )


def test_a_decided_review_needs_an_engineer():
    with pytest.raises(BadValueError):
        a_review(state=ReviewState.APPROVED, decided_on=DECIDED)


def test_a_closed_review_needs_a_decision_day():
    with pytest.raises(BadValueError):
        a_review(state=ReviewState.APPROVED, engineer="R Halloran")


def test_a_decision_may_not_predate_the_opening():
    with pytest.raises(BadValueError):
        a_review().approved_by("R Halloran", OPENED - dt.timedelta(days=1))


def test_a_decision_on_the_opening_day_is_allowed():
    assert a_review().approved_by("R Halloran", OPENED).days_open == 0


def test_approving_twice_is_refused():
    made = a_review().approved_by("R Halloran", DECIDED)
    with pytest.raises(NotAllowedError):
        made.approved_by("R Halloran", DECIDED)


def test_refusing_an_approved_review_is_refused():
    made = a_review().approved_by("R Halloran", DECIDED)
    with pytest.raises(NotAllowedError):
        made.refused_by("R Halloran", DECIDED, "changed my mind")


def test_withdrawing_a_refused_review_is_refused():
    made = a_review().refused_by("R Halloran", DECIDED, "no")
    with pytest.raises(NotAllowedError):
        made.withdrawn(DECIDED)


def test_too_many_conditions_are_refused():
    many = tuple(f"condition {n}" for n in range(MAX_CONDITIONS + 1))
    with pytest.raises(BadValueError):
        a_review().approved_by("R Halloran", DECIDED, many)


def test_the_most_conditions_are_allowed():
    many = tuple(f"condition {n}" for n in range(MAX_CONDITIONS))
    assert len(a_review().approved_by("R Halloran", DECIDED, many).conditions) == MAX_CONDITIONS


def test_an_empty_condition_is_refused():
    with pytest.raises(BadValueError):
        a_review().approved_by("R Halloran", DECIDED, ("  ",))


def test_an_engineer_name_that_is_too_long_is_refused():
    with pytest.raises(BadValueError):
        a_review().approved_by("x" * (MAX_ENGINEER + 1), DECIDED)


def test_a_note_that_is_not_text_is_refused():
    with pytest.raises(BadValueError):
        a_review(state=ReviewState.WITHDRAWN, decided_on=DECIDED, note=12)


def test_the_closed_states_are_the_three_that_end_it():
    assert {ReviewState.APPROVED, ReviewState.REFUSED, ReviewState.WITHDRAWN} == CLOSED


def test_a_review_prints_its_engineer():
    made = a_review().approved_by("R Halloran", DECIDED)
    assert str(made) == "E-00001 application 3 approved by R Halloran"


def test_an_open_review_prints_without_an_engineer():
    assert str(a_review()) == "E-00001 application 3 open"
