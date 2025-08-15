import datetime as dt

import pytest

from jeepdolly.billing.invoice import Invoice, feet_over, price
from jeepdolly.billing.tariff import SCHEDULE, FeeLine
from jeepdolly.errors import BadValueError, NotFoundError
from jeepdolly.permit.application import ANNUAL_DAYS, Application, Kind
from jeepdolly.rig.load import Load
from jeepdolly.units.clock import DaySpan
from jeepdolly.units.distance import miles
from jeepdolly.units.length import feet, feet_inches
from jeepdolly.units.mass import pounds
from jeepdolly.units.money import cents

FILED = dt.date(2025, 6, 16)
TRIP = DaySpan(dt.date(2025, 6, 18), dt.date(2025, 6, 20))
YEAR = DaySpan(dt.date(2025, 7, 1), dt.date(2025, 7, 1) + dt.timedelta(days=ANNUAL_DAYS - 1))


def a_load(**over: object) -> Load:
    kw: dict[str, object] = {
        "description": "step-up transformer",
        "weight": pounds(148000),
        "width": feet_inches(8, 6),
        "height": feet_inches(13, 6),
        "length": feet(48),
        "divisible": False,
        "reason": "single-piece",
    }
    kw.update(over)
    return Load(**kw)  # type: ignore[arg-type]


def an_application(**over: object) -> Application:
    kw: dict[str, object] = {
        "carrier": "VANCE",
        "rig": "R-00001",
        "load": a_load(),
        "span": TRIP,
        "filed_on": FILED,
        "kind": Kind.TRIP,
        "origin": "JCT-A",
        "destination": "JCT-D",
    }
    kw.update(over)
    return Application(**kw)  # type: ignore[arg-type]


def an_annual(**over: object) -> Application:
    return an_application(kind=Kind.ANNUAL, span=YEAR, origin=None, destination=None, **over)


def test_feet_over_is_zero_at_the_limit():
    assert feet_over(feet(8), feet(8)) == 0


def test_feet_over_rounds_an_inch_up_to_a_foot():
    assert feet_over(feet_inches(8, 1), feet(8)) == 1


def test_feet_over_at_an_exact_foot():
    assert feet_over(feet(10), feet(8)) == 2


def test_feet_over_one_inch_past_an_exact_foot():
    assert feet_over(feet_inches(10, 1), feet(8)) == 3


def test_a_plain_trip_gets_a_base_and_a_mileage_line():
    made = price(an_application(), pounds(0), miles("42.00"))
    assert made.codes == ("TRIP", "MILES")


def test_the_base_line_is_the_trip_rate():
    made = price(an_application(), pounds(0), miles("42.00"))
    assert made.line("TRIP").amount == SCHEDULE.trip_base


def test_the_mileage_line_bills_whole_miles():
    made = price(an_application(), pounds(0), miles("42.01"))
    assert int(made.line("MILES").amount) == 43 * 6


def test_the_total_is_the_sum_of_the_lines():
    made = price(an_application(), pounds(0), miles("42.00"))
    assert int(made.total) == int(SCHEDULE.trip_base) + 42 * 6


def test_an_annual_has_no_mileage_line():
    made = price(an_annual(), pounds(0))
    assert made.codes == ("ANNUAL",)


def test_an_annual_refuses_a_distance():
    with pytest.raises(BadValueError):
        price(an_annual(), pounds(0), miles("42.00"))


def test_a_trip_refuses_a_missing_distance():
    with pytest.raises(BadValueError):
        price(an_application(), pounds(0))


def test_a_superload_gets_its_own_base():
    made = price(an_application(kind=Kind.SUPERLOAD), pounds(0), miles("42.00"))
    assert made.line("SUPER").amount == SCHEDULE.superload_base


def test_an_overweight_line_appears():
    made = price(an_application(), pounds(20000), miles("42.00"))
    assert made.has("WEIGHT")


def test_the_overweight_line_bills_whole_tons():
    made = price(an_application(), pounds(20001), miles("42.00"))
    assert "11 tons" in made.line("WEIGHT").detail


def test_no_overweight_line_when_there_is_no_excess():
    made = price(an_application(), pounds(0), miles("42.00"))
    assert not made.has("WEIGHT")


def test_a_wide_load_gets_a_width_line():
    made = price(an_application(load=a_load(width=feet(12))), pounds(0), miles("42.00"))
    assert int(made.line("WIDTH").amount) == 4 * 1000


def test_a_load_one_inch_over_is_charged_a_whole_foot():
    made = price(
        an_application(load=a_load(width=feet_inches(8, 7))), pounds(0), miles("42.00")
    )
    assert int(made.line("WIDTH").amount) == 1000


def test_a_tall_load_gets_a_height_line():
    made = price(an_application(load=a_load(height=feet(15))), pounds(0), miles("42.00"))
    assert int(made.line("HEIGHT").amount) == 2 * 1500


def test_a_legal_load_gets_neither_size_line():
    made = price(an_application(), pounds(0), miles("42.00"))
    assert not made.has("WIDTH")
    assert not made.has("HEIGHT")


def test_the_escorts_are_billed_by_the_head():
    made = price(an_application(), pounds(0), miles("42.00"), escorts=2)
    assert int(made.line("ESCORT").amount) == 2 * 1500


def test_no_escort_line_when_there_are_none():
    made = price(an_application(), pounds(0), miles("42.00"))
    assert not made.has("ESCORT")


def test_the_lines_come_out_in_the_schedule_order():
    made = price(
        an_application(load=a_load(width=feet(12), height=feet(15))),
        pounds(20000),
        miles("42.00"),
        escorts=2,
    )
    assert made.codes == ("TRIP", "MILES", "WEIGHT", "WIDTH", "HEIGHT", "ESCORT")


def test_the_total_adds_every_line():
    made = price(
        an_application(load=a_load(width=feet(12), height=feet(15))),
        pounds(20000),
        miles("42.00"),
        escorts=2,
    )
    assert int(made.total) == sum(int(line.amount) for line in made.lines)


def test_line_raises_for_a_code_that_is_not_there():
    made = price(an_application(), pounds(0), miles("42.00"))
    with pytest.raises(NotFoundError):
        made.line("ESCORT")


def test_an_invoice_refuses_two_lines_with_one_code():
    line = FeeLine(code="TRIP", detail="x", amount=cents(1))
    with pytest.raises(BadValueError):
        Invoice(lines=(line, line))


def test_an_empty_invoice_costs_nothing():
    made = Invoice(lines=())
    assert int(made.total) == 0
    assert len(made) == 0


def test_an_invoice_prints_its_count_and_total():
    made = price(an_application(), pounds(0), miles("42.00"))
    assert str(made) == "2 lines, $27.52"


def test_a_bigger_overage_never_costs_less():
    previous = 0
    for tons in range(40):
        made = price(an_application(), pounds(tons * 2000), miles("42.00"))
        assert int(made.total) >= previous
        previous = int(made.total)
