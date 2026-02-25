# jeepdolly

Permit records for a state oversize and overweight highway permit office.

A carrier who wants to move a load that is too heavy or too big for the ordinary
statutory limits has to buy a permit first. This is the office side of that: the
rig as it is actually built, the limits it has to clear, the route it has to
take, the hours it is allowed to run, and what the move costs.

Everything is one sqlite file. There is no server and no background worker.

    jeepdolly init permits.sqlite3
    jeepdolly carrier add --name "Vance Heavy Haul" --usdot 1184062
    jeepdolly rig build --carrier VANCE --config 3S2
    jeepdolly permit apply --carrier VANCE --rig R-0001 --from JCT-12 --to JCT-31

The name is trade slang. A jeep dolly is the extra axle set you drop between
the tractor and the trailer to spread gross weight across more axles, which is
often the difference between a load that permits and one that does not.

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
