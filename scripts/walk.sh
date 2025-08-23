#!/usr/bin/env bash
# A season at the counter, run against whatever `jeepdolly` is on the PATH.
#
# This is the check that the parts still work together once they are installed
# rather than imported from the source tree. It builds an office from nothing,
# maps a corridor, records rigs, takes applications, issues permits, amends one,
# voids another, and prints every report. Any non zero exit fails the build.
set -euo pipefail

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
office="$work/office.sqlite3"
run() { jeepdolly -f "$office" "$@"; }

echo "== opening the office =="
run init
run status

echo "== carriers =="
run carrier add --code VANCE --name "Vance Heavy Haul" --usdot 1184062 --state MT
run carrier add --code SUMMIT --name "Summit Rigging" --usdot 2277431 --state ID
run carrier add --code OLDCO --name "Oldco Transport" --usdot 3311902 --state WY
run carrier list
run carrier show VANCE
run carrier retire OLDCO
run carrier list
run carrier list --all
run carrier search rigging
run carrier restore OLDCO

echo "== the map =="
run road node --code JCT-A --name "US 12 at Lolo" --county Missoula
run road node --code JCT-B --name "US 12 at Sixmile" --county Missoula
run road node --code JCT-C --name "SR 200 junction" --county Granite
run road node --code JCT-D --name "Anaconda yard gate" --county Deer-Lodge
run road segment --code SEG-AB --start JCT-A --end JCT-B --route US-12 --miles 12.00
run road segment --code SEG-BC --start JCT-B --end JCT-C --route US-12 --miles 8.50
run road segment --code SEG-CD --start JCT-C --end JCT-D --route US-12 --miles 6.00 --posted 48,000
run road segment --code SEG-BD --start JCT-B --end JCT-D --route SR-200 --miles 31.00 --class state
run road structure --segment SEG-BC --name "Sixmile Creek" --milepost 4.20 --rating 64,000
run road structure --segment SEG-BC --name "MRL overhead" --kind overhead --milepost 1.10 --clearance "15'2"
run road structure --segment SEG-BD --name "Clark Fork bridge" --milepost 18.40 --rating 96,000
run road map

echo "== rigs =="
run rig build --carrier VANCE --name 3S2
run rig build --carrier SUMMIT --name 3S4 \
  --axle 12000,2,11,0 --axle 21000,4,11,15 --axle 21000,4,11,4 \
  --axle 21000,8,11,26 --axle 21000,8,11,5 --axle 21000,8,11,5
run rig list
run rig show R-00001
run rig show R-00002

echo "== accounts =="
run account deposit VANCE --amount 2,500.00 --on 2025-06-01 --note "opening deposit"
run account deposit SUMMIT --amount 500.00 --on 2025-06-01
run account floor SUMMIT --amount -2,000.00
run account statement VANCE
run account owing

echo "== a straightforward trip =="
run permit apply --carrier VANCE --rig R-00001 \
  --description "step-up transformer" --weight 148,000 \
  --width "12'6" --height "14'2" --length "48'" \
  --first 2025-06-18 --last 2025-06-20 \
  --origin JCT-A --destination JCT-D --filed 2025-06-16
run permit quote 1 --on 2025-06-17
run permit issue 1 --on 2025-06-17
run permit show P-000001
run account charge VANCE --permit P-000001 --on 2025-06-17
run report permit P-000001

echo "== a load that has to take the long way =="
run permit apply --carrier SUMMIT --rig R-00002 \
  --description "bucket wheel section" --weight 210,000 \
  --width "15'0" --height "15'8" --length "62'" --rear-overhang "9'" \
  --first 2025-07-07 --last 2025-07-09 \
  --origin JCT-A --destination JCT-D --filed 2025-07-01
run permit quote 2 --on 2025-07-02
run permit issue 2 --on 2025-07-02
run account charge SUMMIT --permit P-000002 --on 2025-07-02
run report permit P-000002

echo "== one that cannot be permitted =="
run permit apply --carrier VANCE --rig R-00001 \
  --description "crane boom section" --weight 96,000 \
  --width "10'0" --height "18'0" --length "70'" \
  --first 2025-07-14 --last 2025-07-15 \
  --origin JCT-A --destination JCT-D --filed 2025-07-10
run permit quote 3 --on 2025-07-11

echo "== an annual =="
run permit apply --carrier VANCE --rig R-00001 --kind annual \
  --description "assorted nondivisible plant" --weight 92,000 \
  --width "10'0" --height "13'6" --length "53'" \
  --first 2025-08-01 --last 2026-07-31 --filed 2025-07-20
run permit quote 4 --on 2025-07-21
run permit issue 4 --on 2025-07-21

echo "== amendments and voids =="
run permit extend P-000001 --last 2025-06-22
run permit void P-000002 --reason "carrier cancelled the move" --on 2025-07-03
run permit list
run permit list --carrier VANCE
run permit list --on 2025-06-19

echo "== reports =="
run report route --from JCT-A --to JCT-D
run report day 2025-06-19
run report revenue
run report revenue --first 2025-06-01 --last 2025-06-30
run account statement VANCE
run account statement SUMMIT --first 2025-07-01 --last 2025-07-31
run account owing
run status

echo "walk: clean"
