# jeepdolly

Permit records for a state oversize and overweight highway permit office.

A carrier who wants to move a load that is too heavy or too big for the ordinary
statutory limits has to buy a permit first. This is the office side of that: the
rig as it is actually built, the limits it has to clear, the route it has to
take, the hours it is allowed to run, and what the move costs.

Everything is one sqlite file. There is no server and no background worker.

The name is trade slang. A jeep dolly is the extra axle set you drop between the
tractor and the trailer to spread gross weight across more axles, which is often
the difference between a load that permits and one that does not.

## A morning at the counter

    jeepdolly init permits.sqlite3
    jeepdolly almanac holidays 2026
    jeepdolly carrier add --code VANCE --name "Vance Heavy Haul" --usdot 1184062 --state MT
    jeepdolly rig build --carrier VANCE --name 3S2
    jeepdolly permit apply --carrier VANCE --rig R-00001 \
      --description "step-up transformer" --weight 148,000 \
      --width "12'6" --height "14'2" --length "48'" \
      --first 2026-06-18 --last 2026-06-20 --origin JCT-A --destination JCT-D
    jeepdolly permit quote 1
    jeepdolly permit issue 1
    jeepdolly report permit P-000001

`scripts/walk.sh` is the same thing at length: a whole season through an
installed copy, every command exercised, run by the build.

## What it works out

**The weight.** The flat statutory limits, the federal bridge formula over every
run of axles, and the tire width rule. A finding names the axle or the group, the
rule, and how many pounds over it is.

**The road.** A map of junctions and the stretches between them, with the bridges
and overheads built on them. Routing finds the shortest way a *given rig* can
actually be driven, which is usually not the shortest way.

**The calendar.** Frost laws that cut the axle limits in spring, the winter
premium that raises them, holiday embargoes worked out rather than typed in, and
rush hour restrictions by county. A permit is decided against the orders in force
on the day it is good for, not the day it is written.

**The money.** A banded, progressive overweight charge, per mile, per foot over
width and height, and per escort vehicle. Fees are cents, distances are
hundredths of a mile, and nothing rounds twice.

**The paperwork.** The printed permit, the route sheet, the day sheet, the
movement plan, the staging, the carrier file, the revenue return, the workload
return and a three way audit of permits against accounts against the journal.

## Reading further

- `docs/design.md` — how the package is put together, and why
- `docs/commands.md` — every command, generated from the command tree
- `docs/schema.md` — every table, generated from a migrated file
- `docs/glossary.md` — the office's words, generated from the code that declares them

## Building it

    python -m pip install -e . -c constraints.txt
    python -m pytest
    for check in src/jeepdolly/tools/check_*.py; do python "$check"; done

The stack is pinned to early 2025 in `constraints.txt`, transitive dependencies
included. Installing without it walks forward and the 3.13 leg of the build
starts reporting warnings that have nothing to do with this code.

Nineteen checks run beside the tests. They enforce the import layering, the
`__all__` lists, the docstrings, the SQL parameterisation, the module boundaries,
the test naming, the fixture hygiene, the migration fingerprints, the absence of
unfinished notes, the dataclass shape, the foreign key indexes, the dependency
pinning, the design document's references, and that every command is reached by
both the suite and the walk script. Each exists because something it now catches
got past review at least once.
