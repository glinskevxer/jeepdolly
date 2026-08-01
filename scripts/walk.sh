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

echo "== the almanac =="
run almanac holidays 2025
run almanac season --code THAW-25 --first 2025-03-01 --last 2025-04-15 \
  --percent 60 --counties "Missoula, Granite" --note "spring thaw"
run almanac embargo --code RUSH-MSO --first 2025-06-01 --last 2025-08-31 \
  --reason "peak traffic on Reserve Street" --from-time 07:00 --to-time 09:00 \
  --counties Missoula
run almanac list
run almanac on 2025-07-03 --county Missoula

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
run carrier contact VANCE --name "Ruth Halloran" --number "(406) 555-0142" \
  --email ruth@vance.example --primary
run carrier contact VANCE --role accounts --name "Dale Okonkwo" --number 4065550188
run carrier contact SUMMIT --role safety --name "Ana Reyes" --number "406.555.0199"
run carrier contacts VANCE
run carrier primary VANCE --role accounts
run carrier ring 406-555-0142

echo "== the paper a carrier has lodged =="
run carrier lodge VANCE --cover "surety bond" --insurer "Cascade Surety" \
  --policy SB-4471 --amount 250000 --from 2025-01-01 --to 2025-12-31
run carrier lodge VANCE --cover "public liability" --insurer "Bitterroot Mutual" \
  --policy PL-88120 --amount 5000000 --from 2025-01-01 --to 2025-12-31
run carrier lodge VANCE --cover cargo --insurer "Bitterroot Mutual" \
  --policy CG-88121 --amount 250000 --from 2025-01-01 --to 2025-12-31
run carrier lodge SUMMIT --cover "surety bond" --insurer "Cascade Surety" \
  --policy SB-5510 --amount 50000 --from 2025-01-01 --to 2025-07-31
run carrier paper VANCE --on 2025-07-03
run carrier cover VANCE --kind superload --on 2025-07-03
# Summit holds a bond and nothing else, so this one is meant to come back short.
run carrier cover SUMMIT --on 2025-07-03 || echo "summit is short, as expected"
run carrier chase --within 120 --on 2025-07-03

echo "== bulk loading a feed =="
feed="$work/feed"
mkdir -p "$feed"
cat > "$feed/nodes.csv" <<'CSV'
code,name,county
JCT-W,US 93 at Florence,Ravalli
JCT-X,US 93 at Hamilton,Ravalli
CSV
cat > "$feed/segments.csv" <<'CSV'
code,start,end,route,miles,class,max_width,max_height
SEG-WX,JCT-W,JCT-X,US-93,18.40,state,16',17'
CSV
run load "$feed"
run check

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
run road structure --segment SEG-BC --name "MRL overhead" --kind overhead --milepost 1.10 \
  --clearance "15'2" --owner "Montana Rail Link" --notice-days 10
run road structure --segment SEG-BD --name "Clark Fork bridge" --milepost 18.40 --rating 150,000
run road structure --segment SEG-BD --name "Reserve Street crossing" --kind overhead \
  --milepost 6.30 --clearance "16'0" --owner "Missoula Electric" --notice-days 3
run road map
run road owners
run road owners --owner "Missoula Electric"

echo "== rigs =="
run rig build --carrier VANCE --name 3S2
run rig build --carrier SUMMIT --name 3S4 \
  --axle 12000,2,11,0 --axle 21000,4,11,15 --axle 21000,4,11,4 \
  --axle 21000,8,11,26 --axle 21000,8,11,5 --axle 21000,8,11,5
run rig list
run rig show R-00001
run rig show R-00002
run rig advise R-00001
run rig advise R-00002
run rig advise R-00002 --class state --count 2

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
run permit advise 3

echo "== an annual =="
run permit apply --carrier VANCE --rig R-00001 --kind annual \
  --description "assorted nondivisible plant" --weight 92,000 \
  --width "10'0" --height "13'6" --length "53'" \
  --first 2025-08-01 --last 2026-07-31 --filed 2025-07-20
run permit quote 4 --on 2025-07-21
run permit issue 4 --on 2025-07-21

echo "== a superload in front of an engineer =="
run permit apply --carrier SUMMIT --rig R-00002 \
  --description "cold box shell" --weight 180,000 \
  --width "17'0" --height "15'0" --length "60'" --kind superload \
  --first 2025-08-11 --last 2025-08-13 \
  --origin JCT-A --destination JCT-D --filed 2025-08-01
run review open 5 --on 2025-08-02
run review list
run review approve E-00001 --engineer "R Halloran" --on 2025-08-04 \
  --condition "walking pace over the Clark Fork bridge" \
  --condition "county notified twenty four hours ahead"
run review list --all
run permit issue 5 --on 2025-08-04

echo "== one an engineer will not sign =="
run permit apply --carrier SUMMIT --rig R-00002 \
  --description "gantry leg" --weight 150,000 \
  --width "18'0" --height "15'0" --length "70'" --kind superload \
  --first 2025-09-08 --last 2025-09-10 \
  --origin JCT-A --destination JCT-D --filed 2025-09-01
run review open 6 --on 2025-09-02
run review refuse E-00002 --engineer "R Halloran" --on 2025-09-04 \
  --note "the Clark Fork bridge will not take it at that width"
run review list --all
run account charge SUMMIT --permit P-000004 --on 2025-08-04

echo "== amendments and voids =="
run permit amendments P-000001
run permit amend P-000001 --destination JCT-C --note "shipper moved the delivery" \
  --on 2025-06-18
run permit amend P-000001 --width 13ft --on 2025-06-18
run permit amendments P-000001
run permit extend P-000001 --last 2025-06-22
run permit void P-000002 --cause "carrier cancelled" --on 2025-07-03
run permit void P-000004 --cause "load was not as declared" \
  --detail "steel coil on the trailer, transformer on the application" --on 2025-08-05
run permit list
run permit list --carrier VANCE
run permit list --on 2025-06-19
run permit renew P-000003 --on 2026-07-15

echo "== enforcement =="
run enforce tickets P-000001
run enforce weigh P-000001 --axle 12,000 --axle 17,000 --axle 17,000 --axle 17,000 \
  --axle 17,000 --place "Bonner scales" --officer "Sgt Ramos" --on 2025-06-19
run enforce weigh P-000003 --axle 20,000 --axle 25,000 --axle 25,000 --axle 25,000 \
  --axle 25,000 --place "Clinton scales" --officer "Sgt Ramos" --on 2026-07-09
run enforce tickets P-000001
run enforce ticket WT-00002
run enforce record VANCE
run enforce record SUMMIT

echo "== reports =="
run report route --from JCT-A --to JCT-D
run report detour --from JCT-A --to JCT-D --rig R-00001 --closed SEG-BD
run report day 2025-06-19
run report carrier VANCE
run report schedule P-000001
run report stage P-000001 --speed 30
run report expiring 2025-06-19
run report notices P-000001 --on 2025-06-01
run report audit
run report workload
run report revenue
run report revenue --first 2025-06-01 --last 2025-06-30
run account statement VANCE
run account statement SUMMIT --first 2025-07-01 --last 2025-07-31
run account owing
run history show
run history show --about P-000001
run history kinds
run office sound
run office rows
run office vacuum
run office backup "$work/nightly.sqlite3"
run status

echo "walk: clean"
