# Second-annotator brief: is this story relevant?

You've been asked to help check a search system by judging, for a list of
questions, whether a candidate answer actually answers each one. You do not
need to know anything about Buddhism, Pali, or this project's code — you
just need to read English text and make a judgment call. This should take
**about 60-90 minutes** for the full sheet (507 judgments across 72
questions).

## What you're doing

The project retrieves short "stories" (each explains one or more verses of
a Buddhist text, the Dhammapada) in response to a question. One person has
already judged which stories count as a correct answer to each question.
You are a **second, independent judge**, so the project can measure how
much two people agree — a standard check on whether "correct answer" is
being judged consistently, or just according to one person's idiosyncratic
reading.

You will **not** see the first judge's answers, and you should not try to
guess or reverse-engineer them. Judge each row fresh, on its own merits.

## The file

Open `data/eval/annotation_v2_blank.csv` in a spreadsheet program (Excel,
Google Sheets, LibreOffice Calc — anything that opens CSV). It has one row
per (question, candidate story) pair. Columns:

| Column | What it is |
|---|---|
| `question_id` | Groups rows belonging to the same question. Ignore otherwise. |
| `question` | The question being asked. |
| `candidate_group_id` | An internal ID for the candidate story. Ignore. |
| `title` | The candidate story's title. |
| `synopsis` | A short summary of the candidate story. |
| `verse_english` | The English text of the verse(s) that story explains. |
| `relevant` | **You fill this in: `1` or `0`.** |
| `comment` | Optional. Leave blank unless something's worth flagging (see below). |

Several rows share the same `question_id` — that's the same question paired
with different candidate stories. Judge each row independently: it is
completely normal for a question to have several rows marked `1`, or none
at all.

## The rule

> Mark `relevant = 1` if this story — its narrative, or the verse(s) it
> explains — answers or directly bears on the question. Mark `0`
> otherwise. For questions that ask "which stories...", mark **every**
> story that fits, not just one.

Base your judgment only on the `title`, `synopsis`, and `verse_english`
text given in that row. Don't research outside it, and don't look anything
up — the whole point is to capture what a reader would conclude from
exactly this text.

### Worked example

*(This example is illustrative only — it is not one of the real rows in
your sheet.)*

**Question:** "Which story explains why a certain elder was mocked for
falling asleep during a sermon?"

| Candidate title | Synopsis (abridged) | Verdict |
|---|---|---|
| "The Story of the Drowsy Elder" | An elder kept nodding off during the Buddha's teaching, and the other monks laughed. The Buddha spoke this verse about mindfulness in response. | **1** — directly matches the question. |
| "The Story of the Merchant's Debt" | A merchant is pursued by creditors and reflects on impermanence. | **0** — nothing about sleep, mockery, or an elder. |

If a row's synopsis is *close but not quite* — say, it involves a monk
falling asleep but nobody mocks him — mark `0` and use the `comment`
column to note why you hesitated (e.g. "close but no mockery mentioned").
Comments aren't required, but they help if your answer differs from the
other judge's and someone needs to see your reasoning.

## Things not to do

- **Do not open** `data/eval/gold_set_v2.jsonl` or
  `data/eval/retrieval_results_v2.jsonl`. These contain the first judge's
  answers. Opening them defeats the entire point of a second, independent
  opinion.
- Don't search the web or any other source for the "real" answer — judge
  from the text on the row alone.
- Don't leave a row blank. If you're genuinely unsure, pick your best
  judgment and say why in `comment` rather than skipping it — a blank
  `relevant` cell will make the file fail to process.
- Don't reorder or delete rows, and don't rename the file's columns.

## Returning the file

Save your filled-in copy under a new name (e.g.
`annotation_v2_filled_<yourname>.csv`) so the blank template isn't
overwritten, keep it as CSV (not `.xlsx`), and send it back the way you
were asked to. Someone on the project will then run it through
`python -m dhammapada_rag.eval.annotation_sheet kappa <your file>`, which
compares your judgments against the first judge's and reports Cohen's
kappa (a standard agreement statistic) plus a list of every row where you
two disagreed, for review — not to grade you, but to find questions that
are genuinely ambiguous versus ones with a clear right answer.
