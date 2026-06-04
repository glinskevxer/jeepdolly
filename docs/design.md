# How jeepdolly is put together

This is the document to read before changing anything. The generated ones next to
it say what the commands and the schema currently are; this one says why they are
that shape.

## The one idea

A permit is a decision about a rig, on a road, on a day. Those three are
independent of each other and every one of them changes on its own schedule, so
they are three separate things in the code and the only place they meet is the
counter.

- The **rig** is axles and spacings. It does not know what road it is on.
- The **road** is junctions, stretches and the things built on them. It does not
  know what is driving over it.
- The **calendar** is seasonal orders and embargoes. It does not know either.

`permit.desk` is where the three are wired together, and it is the only module
that knows about all of them. Everything below it is testable without a database,
without a map and without a clock.

## The layers

`tools/check_layers.py` holds the table and the build enforces it. Reading down:

| layer | what is there | may reach |
| --- | --- | --- |
| units, errors | inches, pounds, cents, miles, days, shares | nothing |
| ids | codes and office reference numbers | units |
| limits.finding | the vocabulary every check answers in | units, ids |
| rig, party | axles, arrangements, loads, carriers | above |
| limits | the statutes, the bridge formula, sizes | above |
| roadway | the map | above |
| almanac | frost laws, embargoes, holidays | above |
| travel | escorts, hours, movement plans | above |
| route | plans, clearance, searches, detours | above |
| permit.application, billing | requests and money | above |
| permit.decision, permit.review | the three answers | above |
| permit.permit | the issued permit | above |
| permit.renewal | next year's application | above |
| store | the sqlite file | above |
| permit.desk | the counter | above |
| report, importer, invariants | paperwork | above |
| cli, tools | the front end and the checks | above |

A module may import from its own layer or any layer below. When something
genuinely belongs elsewhere the answer is to move the module, not to add a line
to the table.

## Decisions worth knowing about

**Everything is an integer.** Inches, pounds, cents and hundredths of a mile.
There is no float anywhere a number matters, and the one place a fraction is
needed, apportionment, uses `fractions.Fraction`.

**Nothing rounds twice.** A rate applied to a quantity rounds once, at the end.
`units.money.at_rate` is the only place that happens and there is a test that
shows two rates added is not the same as their sum applied once.

**A finding, never a boolean.** Every check answers with findings that carry the
subject, the rule, the severity and the excess. "The rig is over" is useless at a
counter; "axle 4 is 2,300 pounds over its 20,000 pound limit" is a conversation.

**Refusing and referring are different.** A load too tall for a bridge is refused
and no fee fixes it. A load wider than the review threshold is referred to an
engineer. `permit.decision.REFERABLE_RULES` is the whole difference and getting
it backwards is expensive in both directions.

**The permit keeps its own working.** Findings, fee lines and escorts are written
out beside the permit rather than recomputed on read, because a permit issued
under last spring's frost laws has to keep showing last spring's numbers.

**Migrations are append only and fingerprinted.** `tools/check_migrations.py`
holds a digest of each one and the build fails if an applied migration is edited.

**The journal is written beside the change.** In the same transaction, so a
change that rolls back takes its entry with it. Nothing derives state from it.

## Things that were wrong once

Kept because the reason is more useful than the rule.

- **A jeep relieves the drives, not the trailer.** The first version had the
  donors on the wrong side of the hitch. Nothing failed; the dolly search just
  reported that no jeep ever helped a rig that was over on the drives, which is
  the one thing carriers buy them for. See `rig.dolly._donors`.
- **A dolly cannot fix gross weight.** Scoring the dolly search on the gross
  limit said every dolly made things worse, which was arithmetically true and
  useless: a dolly adds its own tare to gross. It is scored on the rules another
  axle can actually move. See `rig.spread.spread_score`.
- **`with connection:` does not close a connection.** It is a transaction manager.
  `store.sqlite.opened` exists for that and nothing calls `sqlite3.connect`
  directly, which `tools/check_boundaries.py` enforces.
- **The bridge formula turns over.** Past about `12 * N * (N - 1)` feet, adding an
  axle lowers what the formula allows. That is real and it is why
  `invariants.formula_climbs_with_axles` is stated over the useful range and
  `invariants.crossover` explains it.

## The checks

Eighteen of them, run by the build on both interpreters. Each exists because
something it now catches got past review at least once.

| check | what it refuses |
| --- | --- |
| `check_layers` | an import that reaches up a layer |
| `check_exports` | a public name outside `__all__`, or an `__all__` naming nothing |
| `check_docstrings` | a module or public definition with nothing said about it |
| `check_sql` | a value formatted into a query |
| `check_boundaries` | `sqlite3.connect`, `datetime.now`, `print` or `open` out of place |
| `check_naming` | a test name that says too little |
| `check_fixtures` | a fixture that opens a connection and never closes it |
| `check_migrations` | an applied migration that has been edited |
| `check_todo` | an unfinished note, or a test somebody turned off |
| `check_dataclasses` | a record that is not frozen or does not declare slots |
| `check_indexes` | a foreign key column with nothing indexing it |
| `check_pins` | a loose requirement, or an install that skips the constraints |
| `check_links` | a design document reference to a module that is gone |
| `check_commands` | a command the suite or the walk script never reaches |
| `check_readme` | a README example that would not run |
| `check_version` | the two version numbers drifting apart |
| `check_help` | a help string that is not a printable sentence |
| `check_docs` | a generated document that is out of date |

Two test files hold them to their own standard. `tests/tools/test_check_failures`
hands every check a made up finding and asserts it reports and exits non zero.
`tests/tools/test_check_findings` plants a defect of the exact shape each one is
for, in a temporary tree, and asserts the check names it. A check that has only
ever passed has not been seen working.

## The suite

About twenty seven hundred tests, green on 3.12 and 3.13. The command line tests
build their stocked office once for the session and copy it per test through
sqlite's own backup, which halved the suite's running time and is the only piece
of test machinery here worth knowing about.

`tests/test_season.py` is the one integration test: a year at the counter, run
through the package rather than the command line, in one long function. The order
is the point and splitting it into fixtures would hide the coupling it is there to
exercise. `scripts/walk.sh` is the same thing again through an *installed* copy,
driven from a shell, and the build runs it on both interpreters.

## Where to start reading

`units/mass.py` for the shape of a value type, `limits/bridge.py` for the
arithmetic the whole office turns on, `rig/spread.py` for the search the package
is named after, and `permit/desk.py` for how it all joins up.
