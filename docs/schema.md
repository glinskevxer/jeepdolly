# jeepdolly schema

Generated from a freshly migrated file by `tools/schema_dump.py`.
Run that with `--write` after adding a migration.

Schema version 14.

## account_entry

| column | type | constraints |
| --- | --- | --- |
| carrier_code | TEXT | primary key, not null |
| sequence | INTEGER | primary key, not null |
| day | TEXT | not null |
| kind | TEXT | not null |
| amount | INTEGER | not null |
| reference | TEXT | not null, default '' |
| note | TEXT | not null, default '' |

Indexes: `account_by_day`

## account_terms

| column | type | constraints |
| --- | --- | --- |
| carrier_code | TEXT | primary key |
| floor | INTEGER | not null |

## application

| column | type | constraints |
| --- | --- | --- |
| id | INTEGER | primary key |
| carrier_code | TEXT | not null |
| rig_reference | TEXT | not null |
| load_id | INTEGER | not null |
| kind | TEXT | not null |
| first_day | TEXT | not null |
| last_day | TEXT | not null |
| filed_on | TEXT | not null |
| origin | TEXT |  |
| destination | TEXT |  |

Indexes: `application_by_carrier`, `application_by_day`, `application_by_destination`, `application_by_load`, `application_by_origin`, `application_by_rig`

## carrier

| column | type | constraints |
| --- | --- | --- |
| code | TEXT | primary key |
| name | TEXT | not null |
| usdot | INTEGER | not null |
| home_state | TEXT | not null |
| active | INTEGER | not null, default 1 |

Indexes: `carrier_by_name`

## certificate

| column | type | constraints |
| --- | --- | --- |
| carrier_code | TEXT | primary key, not null |
| cover | TEXT | primary key, not null |
| insurer | TEXT | not null |
| policy | TEXT | primary key, not null |
| amount | INTEGER | not null |
| first_day | TEXT | not null |
| last_day | TEXT | not null |

Indexes: `certificate_by_carrier`, `certificate_by_expiry`

## contact

| column | type | constraints |
| --- | --- | --- |
| carrier_code | TEXT | primary key, not null |
| role | TEXT | primary key, not null |
| name | TEXT | not null |
| number | TEXT | not null |
| email | TEXT | not null, default '' |
| primary_one | INTEGER | not null, default 0 |

Indexes: `contact_by_number`, `contact_one_primary`

## embargo

| column | type | constraints |
| --- | --- | --- |
| code | TEXT | primary key |
| first_day | TEXT | not null |
| last_day | TEXT | not null |
| reason | TEXT | not null |
| window_start | INTEGER |  |
| window_end | INTEGER |  |
| weekends_only | INTEGER | not null, default 0 |

Indexes: `embargo_by_day`

## embargo_county

| column | type | constraints |
| --- | --- | --- |
| embargo_code | TEXT | primary key, not null |
| county | TEXT | primary key, not null |

## journal

| column | type | constraints |
| --- | --- | --- |
| sequence | INTEGER | primary key |
| day | TEXT | not null |
| kind | TEXT | not null |
| subject | TEXT | not null |
| detail | TEXT | not null, default '' |
| clerk | TEXT | not null, default '' |

Indexes: `journal_by_day`, `journal_by_subject`

## load_item

| column | type | constraints |
| --- | --- | --- |
| id | INTEGER | primary key |
| description | TEXT | not null |
| weight | INTEGER | not null |
| width | INTEGER | not null |
| height | INTEGER | not null |
| length | INTEGER | not null |
| front_overhang | INTEGER | not null, default 0 |
| rear_overhang | INTEGER | not null, default 0 |
| divisible | INTEGER | not null, default 1 |
| reason | TEXT | not null, default '' |

## node

| column | type | constraints |
| --- | --- | --- |
| code | TEXT | primary key |
| name | TEXT | not null |
| county | TEXT | not null |

## permit

| column | type | constraints |
| --- | --- | --- |
| number | TEXT | primary key |
| application_id | INTEGER | not null |
| outcome | TEXT | not null |
| decided_on | TEXT | not null |
| issued_on | TEXT | not null |
| first_day | TEXT | not null |
| last_day | TEXT | not null |
| state | TEXT | not null |
| reason | TEXT | not null, default '' |
| replaced_by | TEXT |  |
| distance | INTEGER |  |

Indexes: `permit_by_application`, `permit_by_day`, `permit_by_successor`

## permit_escort

| column | type | constraints |
| --- | --- | --- |
| permit_number | TEXT | primary key, not null |
| position | INTEGER | primary key, not null |
| role | TEXT | not null |
| reasons | TEXT | not null |

## permit_fee_line

| column | type | constraints |
| --- | --- | --- |
| permit_number | TEXT | primary key, not null |
| position | INTEGER | primary key, not null |
| code | TEXT | not null |
| detail | TEXT | not null |
| amount | INTEGER | not null |

## permit_finding

| column | type | constraints |
| --- | --- | --- |
| permit_number | TEXT | primary key, not null |
| position | INTEGER | primary key, not null |
| rule | TEXT | not null |
| subject | TEXT | not null |
| severity | TEXT | not null |
| detail | TEXT | not null |
| excess | INTEGER | not null, default 0 |

## review

| column | type | constraints |
| --- | --- | --- |
| reference | TEXT | primary key |
| application_id | INTEGER | not null |
| opened_on | TEXT | not null |
| state | TEXT | not null |
| engineer | TEXT | not null, default '' |
| decided_on | TEXT |  |
| note | TEXT | not null, default '' |

Indexes: `review_by_application`, `review_by_state`

## review_condition

| column | type | constraints |
| --- | --- | --- |
| review_reference | TEXT | primary key, not null |
| position | INTEGER | primary key, not null |
| text | TEXT | not null |

## rig

| column | type | constraints |
| --- | --- | --- |
| reference | TEXT | primary key |
| carrier_code | TEXT | not null |
| name | TEXT | not null |
| recorded_on | TEXT | not null |

Indexes: `rig_by_carrier`

## rig_axle

| column | type | constraints |
| --- | --- | --- |
| rig_reference | TEXT | primary key, not null |
| position | INTEGER | primary key, not null |
| weight | INTEGER | not null |
| tires | INTEGER | not null |
| tire_width | INTEGER | not null |
| liftable | INTEGER | not null, default 0 |
| steering | INTEGER | not null, default 0 |
| spacing_ahead | INTEGER | not null, default 0 |

## schema_change

| column | type | constraints |
| --- | --- | --- |
| number | INTEGER | primary key |
| name | TEXT | not null |
| ran_at | TEXT | not null, default datetime('now') |

## season

| column | type | constraints |
| --- | --- | --- |
| code | TEXT | primary key |
| first_day | TEXT | not null |
| last_day | TEXT | not null |
| percent | INTEGER | not null |
| note | TEXT | not null, default '' |

Indexes: `season_by_day`

## season_county

| column | type | constraints |
| --- | --- | --- |
| season_code | TEXT | primary key, not null |
| county | TEXT | primary key, not null |

## segment

| column | type | constraints |
| --- | --- | --- |
| code | TEXT | primary key |
| start_node | TEXT | not null |
| end_node | TEXT | not null |
| route | TEXT | not null |
| distance | INTEGER | not null |
| road_class | TEXT | not null |
| one_way | INTEGER | not null, default 0 |
| posted_gross | INTEGER |  |
| max_width | INTEGER |  |
| max_height | INTEGER |  |

Indexes: `segment_by_end`, `segment_by_restriction`, `segment_by_start`

## structure

| column | type | constraints |
| --- | --- | --- |
| reference | TEXT | primary key |
| segment_code | TEXT | not null |
| name | TEXT | not null |
| kind | TEXT | not null |
| milepost | INTEGER | not null |
| clearance | INTEGER |  |
| rating | INTEGER |  |

Indexes: `structure_by_segment`
