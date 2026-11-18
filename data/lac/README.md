# Non-fatal LAC / LoC indicators (Step 5)

The issued data hold one fatal India–China clash in 36 years (Galwan, 15 Jun 2020), so no fatality model can warn
of the next one. This folder is the hook for the non-fatal indicators that can. Drop one CSV per source here,
in the format of `template.csv`, and run `python improve/lac.py`.

| column | meaning |
|---|---|
| date | YYYY-MM-DD of the incident or observation |
| front | `LAC` or `LoC` |
| sector | e.g. `Eastern Ladakh`, `Central`, `Sikkim`, `Arunachal`, `J&K North` |
| indicator | `faceoff`, `patrol_clash`, `buildup`, `infrastructure`, `airspace`, `transgression`, `ceasefire_violation` |
| count | number of events that day |
| severity | 1 (routine) to 3 (serious) |
| source | open source or reporting unit |

Open sources first (press reports, satellite-imagery analyses, parliamentary answers); classified I&W later, on a
secure network. Nothing in this folder ships with the repo except the template.
