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
| units, errors | inches, pounds, cents, days, shares | nothing |
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

Twelve of them, run by the build, each of which exists because something it now
catches got past review at least once. `tools/check_failures` feeds every one of
them a made up finding, because a check that has only ever passed has not been
seen working.

## Where to start reading

`units/mass.py` for the shape of a value type, `limits/bridge.py` for the
arithmetic the whole office turns on, and `permit/desk.py` for how it all joins
up.
