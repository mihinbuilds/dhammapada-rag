# Archive: last generation run with the SuttaCentral verse layer

The generation run, its judgments and its metrics as they stood before Round
13 (2026-10-08). The model's prompt then carried the SuttaCentral Pali and
English for every retrieved verse. Those texts were removed at SuttaCentral's
request (`data/raw/PROVENANCE.md`), so this run cannot be reproduced. It is
kept so the post-removal run in `data/eval/` can be compared with it.

- `generation_raw.jsonl`: SuttaCentral text replaced with
  `[SuttaCentral text removed 2026-10-08]`; source labels renamed.
- `generation_judgments.py`: the 2026-09-23 from-scratch judgments of that run.
- `generation_metrics.json`: the aggregate computed from them.
