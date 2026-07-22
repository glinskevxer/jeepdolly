import datetime as dt

import pytest

from jeepdolly.enforce.ticket import (
    AXLE_TOLERANCE,
    GROSS_TOLERANCE,
    MAX_AXLES,
    Discrepancy,
    Overage,
    Ticket,
    check_ticket,
    worst_axle,
)
from jeepdolly.errors import BadValueError
from jeepdolly.rig.axle import Axle
from jeepdolly.rig.config import Configuration
from jeepdolly.units.length import feet, inches
from jeepdolly.units.mass import pounds

WEIGHED = dt.date(2025, 6, 19)
DECLARED = (12000, 17000, 17000, 17000, 17000)
PERMITTED = pounds(80000)


def a_rig(weights: tuple[int, ...] = DECLARED) -> Configuration:
    """A rig whose axles weigh whatever the caller says."""
    axles = [Axle(weight=pounds(weights[0]), tires=2, tire_width=inches(11), steering=True)]
    axles += [Axle(weight=pounds(one), tires=4, tire_width=inches(11)) for one in weights[1:]]
    return Configuration(
        name="3S2",  # type: ignore[arg-type]
        axles=tuple(axles),
        spacings=tuple(feet(15) for _ in weights[1:]),
    )


def a_ticket(**over: object) -> Ticket:
    """A weight ticket that agrees exactly with the permitted rig."""
    kw: dict[str, object] = {
        "number": "WT-00001",
        "permit": "P-000123",
        "weighed_on": WEIGHED,
        "place": "Bonner scales",
        "officer": "Sgt Ramos",
        "axles": tuple(pounds(one) for one in DECLARED),
    }
    kw.update(over)
    return Ticket(**kw)  # type: ignore[arg-type]


def weighed(axles: tuple[int, ...]) -> Ticket:
    """A ticket carrying these axle weights and nothing else changed."""
    return a_ticket(axles=tuple(pounds(one) for one in axles))


def test_a_ticket_adds_its_own_gross():
    assert int(a_ticket().gross) == sum(DECLARED)


def test_a_ticket_counts_its_axles():
    assert a_ticket().count == 5


def test_a_ticket_names_the_heaviest_axle():
    position, weight = a_ticket(axles=(pounds(1), pounds(9), pounds(2))).heaviest()
    assert position == 2
    assert int(weight) == 9


def test_a_ticket_with_no_axles_is_refused():
    with pytest.raises(BadValueError):
        a_ticket(axles=())


def test_a_ticket_with_too_many_axles_is_refused():
    with pytest.raises(BadValueError):
        a_ticket(axles=tuple(pounds(1000) for _ in range(MAX_AXLES + 1)))


def test_an_axle_weighing_nothing_is_refused():
    with pytest.raises(BadValueError):
        a_ticket(axles=(pounds(12000), pounds(0)))


def test_a_ticket_with_no_place_is_refused():
    with pytest.raises(BadValueError):
        a_ticket(place="   ")


def test_a_ticket_with_no_officer_is_refused():
    with pytest.raises(BadValueError):
        a_ticket(officer="")


def test_a_datetime_weighing_day_is_refused():
    with pytest.raises(BadValueError):
        a_ticket(weighed_on=dt.datetime(2025, 6, 19, tzinfo=dt.UTC))


def test_a_ticket_that_matches_the_permit_finds_nothing():
    assert check_ticket(a_ticket(), a_rig(), PERMITTED) == []


def test_a_rig_inside_the_gross_tolerance_is_left_alone():
    heavy = (12000, 17000, 17000, 17000, 17000 + int(GROSS_TOLERANCE))
    found = check_ticket(weighed(heavy), a_rig(), PERMITTED)
    assert [one.kind for one in found] == [Discrepancy.AXLE]


def test_a_rig_over_the_gross_is_reported():
    heavy = (12000, 17000, 17000, 17000, 30000)
    found = check_ticket(weighed(heavy), a_rig(), PERMITTED)
    assert Discrepancy.GROSS in {one.kind for one in found}


def test_the_gross_overage_is_the_gap_to_the_permit():
    heavy = (12000, 17000, 17000, 17000, 30000)
    found = check_ticket(weighed(heavy), a_rig(), PERMITTED)
    gross = next(one for one in found if one.kind is Discrepancy.GROSS)
    assert int(gross.over) == sum(heavy) - int(PERMITTED)


def test_a_rig_far_lighter_than_permitted_is_reported():
    light = (2000, 2000, 2000, 2000, 2000)
    found = check_ticket(weighed(light), a_rig(), PERMITTED)
    assert Discrepancy.UNDER in {one.kind for one in found}


def test_a_rig_a_little_lighter_is_left_alone():
    found = check_ticket(a_ticket(), a_rig(), pounds(sum(DECLARED) + 1000))
    assert found == []


def test_a_different_number_of_axles_is_reported():
    found = check_ticket(a_ticket(axles=(pounds(12000), pounds(17000))), a_rig(), PERMITTED)
    assert Discrepancy.COUNT in {one.kind for one in found}


def test_a_different_number_of_axles_stops_the_axle_comparison():
    found = check_ticket(a_ticket(axles=(pounds(60000),)), a_rig(), PERMITTED)
    assert Discrepancy.AXLE not in {one.kind for one in found}


def test_an_axle_inside_the_tolerance_is_left_alone():
    close = (12000, 17000, 17000, 17000, 17000 + int(AXLE_TOLERANCE))
    assert worst_axle(weighed(close), a_rig()) is None


def test_an_axle_over_the_tolerance_is_reported():
    over = (12000, 17000, 17000, 17000, 17000 + int(AXLE_TOLERANCE) + 1)
    found = worst_axle(weighed(over), a_rig())
    assert found is not None
    assert found.subject == "axle 5"


def test_the_worst_axle_is_the_one_reported():
    over = (12000, 19000, 17000, 25000, 17000)
    found = worst_axle(weighed(over), a_rig())
    assert found is not None
    assert found.subject == "axle 4"


def test_axles_are_compared_in_order_and_not_paired_by_weight():
    swapped = (17000, 12000, 17000, 17000, 17000)
    found = worst_axle(weighed(swapped), a_rig())
    assert found is not None
    assert found.subject == "axle 1"


def test_a_mismatched_axle_count_gives_no_axle_answer():
    assert worst_axle(a_ticket(axles=(pounds(60000),)), a_rig()) is None


def test_something_that_is_not_a_rig_is_refused():
    with pytest.raises(BadValueError):
        worst_axle(a_ticket(), "3S2")  # type: ignore[arg-type]


def test_something_that_is_not_a_ticket_is_refused():
    with pytest.raises(BadValueError):
        check_ticket("WT-00001", a_rig(), PERMITTED)  # type: ignore[arg-type]


def test_an_overage_with_no_subject_is_refused():
    with pytest.raises(BadValueError):
        Overage(kind=Discrepancy.GROSS, subject="  ", over=pounds(1))


def test_an_overage_prints_how_far_over():
    line = str(Overage(kind=Discrepancy.GROSS, subject="gross", over=pounds(2000)))
    assert "2,000" in line


def test_an_overage_of_nothing_prints_without_a_figure():
    line = str(Overage(kind=Discrepancy.COUNT, subject="2 axles weighed", over=pounds(0)))
    assert "by" not in line


def test_a_ticket_prints_the_permit_and_the_gross():
    line = str(a_ticket())
    assert "P-000123" in line
    assert "Bonner scales" in line
