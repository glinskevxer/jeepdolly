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
