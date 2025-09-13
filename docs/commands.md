# jeepdolly commands

Generated from the command tree by `tools/build_docs.py`.
Run that with `--write` after changing a command, or the build will say so.

Package version 0.1.0.

## commands

### `jeepdolly account`

Take money, charge permits and print statements.

### `jeepdolly account charge`

Charge a permit to a carrier's account.

| name | kind | what it is for |
| --- | --- | --- |
| `carrier` | argument |  |
| `--permit` | required option | Which permit is being charged. |
| `--amount` | option | Override the permit's own fee. |
| `--on` | option | Day the charge is posted. |

### `jeepdolly account deposit`

Take money onto a carrier's account.

| name | kind | what it is for |
| --- | --- | --- |
| `carrier` | argument |  |
| `--amount` | required option | How much is being taken. |
| `--on` | option | Day the money was taken. |
| `--note` | option | Anything worth recording. |

### `jeepdolly account floor`

Set a carrier's credit floor.

| name | kind | what it is for |
| --- | --- | --- |
| `carrier` | argument |  |
| `--amount` | required option | How far into the red this carrier may go. |

### `jeepdolly account owing`

List the carriers with a negative balance.

### `jeepdolly account statement`

Print a carrier's statement.

| name | kind | what it is for |
| --- | --- | --- |
| `carrier` | argument |  |
| `--first` | option | First day of the statement. |
| `--last` | option | Last day of the statement. |

### `jeepdolly carrier`

Add, list and retire carriers.

### `jeepdolly carrier add`

Put a new carrier on file.

| name | kind | what it is for |
| --- | --- | --- |
| `--code` | required option | The office's short key for this carrier. |
| `--name` | required option | The trading name. |
| `--usdot` | required option | The federal number. |
| `--state` | required option | Two letter home state. |

### `jeepdolly carrier list`

List carriers, active ones by default.

| name | kind | what it is for |
| --- | --- | --- |
| `--all` | flag | Include retired carriers. |

### `jeepdolly carrier restore`

Let a retired carrier be issued permits again.

| name | kind | what it is for |
| --- | --- | --- |
| `code` | argument |  |

### `jeepdolly carrier retire`

Stop a carrier being issued new permits.

| name | kind | what it is for |
| --- | --- | --- |
| `code` | argument |  |

### `jeepdolly carrier search`

Find carriers by part of a name or code.

| name | kind | what it is for |
| --- | --- | --- |
| `text` | argument |  |

### `jeepdolly carrier show`

Show one carrier.

| name | kind | what it is for |
| --- | --- | --- |
| `code` | argument |  |

### `jeepdolly check`

Read the whole file back and say whether it holds together.

### `jeepdolly init`

Make a new office file.

### `jeepdolly load`

Bulk load carriers and the map from a folder of csv files.

| name | kind | what it is for |
| --- | --- | --- |
| `folder` | argument |  |

### `jeepdolly permit`

Apply for, price and issue permits.

### `jeepdolly permit apply`

Take an application at the counter.

| name | kind | what it is for |
| --- | --- | --- |
| `--carrier` | required option | Whose permit this is. |
| `--rig` | required option | Which rig, by reference. |
| `--description` | required option | What is on the trailer. |
| `--weight` | required option | Load weight. |
| `--width` | required option | Load width. |
| `--height` | required option | Load height. |
| `--length` | required option | Deck length. |
| `--front-overhang` | option | Front overhang. |
| `--rear-overhang` | option | Rear overhang. |
| `--reason` | option | Why the load cannot be split. |
| `--divisible` | flag | The load can be split up. |
| `--kind` | option | What sort of permit. |
| `--first` | required option | First day the permit is good. |
| `--last` | required option | Last day the permit is good. |
| `--origin` | option | Junction the run starts at. |
| `--destination` | option | Junction the run ends at. |
| `--filed` | option | Day the application was taken. |

### `jeepdolly permit extend`

Push a permit's last day back.

| name | kind | what it is for |
| --- | --- | --- |
| `number` | argument |  |
| `--last` | required option | New last day. |

### `jeepdolly permit issue`

Decide an application and write the permit.

| name | kind | what it is for |
| --- | --- | --- |
| `key` | argument |  |
| `--on` | option | Day the permit is issued. |

### `jeepdolly permit list`

List permits, filtered by carrier or by day.

| name | kind | what it is for |
| --- | --- | --- |
| `--carrier` | option | Only this carrier's permits. |
| `--on` | option | Only permits good on this day. |

### `jeepdolly permit quote`

Price an application without issuing anything.

| name | kind | what it is for |
| --- | --- | --- |
| `key` | argument |  |
| `--on` | option | Day the decision is made. |

### `jeepdolly permit show`

Print one permit.

| name | kind | what it is for |
| --- | --- | --- |
| `number` | argument |  |

### `jeepdolly permit void`

Void an issued permit and refund what was charged for it.

| name | kind | what it is for |
| --- | --- | --- |
| `number` | argument |  |
| `--reason` | required option | Why the permit is being voided. |
| `--on` | option | Day the void is recorded. |
| `--no-refund` | flag | Leave the account alone. |

### `jeepdolly report`

Print the office's paperwork.

### `jeepdolly report day`

Print the movement sheet for one day.

| name | kind | what it is for |
| --- | --- | --- |
| `day` | argument |  |

### `jeepdolly report permit`

Print one permit as it goes in the cab.

| name | kind | what it is for |
| --- | --- | --- |
| `number` | argument |  |

### `jeepdolly report revenue`

Print the revenue return.

| name | kind | what it is for |
| --- | --- | --- |
| `--first` | option | First day of the return. |
| `--last` | option | Last day of the return. |

### `jeepdolly report route`

Print the route sheet between two junctions.

| name | kind | what it is for |
| --- | --- | --- |
| `--from` | required option | Junction the run starts at. |
| `--to` | required option | Junction the run ends at. |

### `jeepdolly rig`

Record rigs and read them back.

### `jeepdolly rig build`

Record a rig, axle by axle.

| name | kind | what it is for |
| --- | --- | --- |
| `--carrier` | required option | Whose rig this is. |
| `--name` | required option | The carrier's shorthand, like 3S2. |
| `--axle` | option | One axle as weight,tires,tire width,spacing ahead. Repeat per axle. |
| `--on` | option | Day the rig was recorded. |

### `jeepdolly rig list`

List rigs, filtered by carrier.

| name | kind | what it is for |
| --- | --- | --- |
| `--carrier` | option | Only this carrier's rigs. |

### `jeepdolly rig show`

Print one rig, axle by axle.

| name | kind | what it is for |
| --- | --- | --- |
| `reference` | argument |  |

### `jeepdolly road`

Put junctions, stretches and structures on the map.

### `jeepdolly road map`

Print the map, one stretch per line.

### `jeepdolly road node`

Put a junction on the map.

| name | kind | what it is for |
| --- | --- | --- |
| `--code` | required option | The office's key for the junction. |
| `--name` | required option | What the route sheet calls it. |
| `--county` | required option | Which county it sits in. |

### `jeepdolly road segment`

Put a stretch of road on the map.

| name | kind | what it is for |
| --- | --- | --- |
| `--code` | required option | The office's key for the stretch. |
| `--start` | required option | Junction it leaves. |
| `--end` | required option | Junction it reaches. |
| `--route` | required option | Route designation, like US-12. |
| `--miles` | required option | Length, to a hundredth. |
| `--class` | option | Which limit set applies. |
| `--one-way` | flag | Only travelled start to end. |
| `--posted` | option | Local gross order, if there is one. |

### `jeepdolly road structure`

Put something in the way on a stretch.

| name | kind | what it is for |
| --- | --- | --- |
| `--segment` | required option | Which stretch it sits on. |
| `--name` | required option | What the bridge crew calls it. |
| `--kind` | option | What sort of thing it is. |
| `--milepost` | required option | Where on the stretch it sits. |
| `--clearance` | option | Posted height, for an overhead. |
| `--rating` | option | Posted load, for a bridge. |

### `jeepdolly status`

Say what is in the office file.
