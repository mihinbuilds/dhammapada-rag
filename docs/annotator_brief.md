# Second-annotator brief: is this story relevant?

You've been asked to help check a search system by judging, for a list of
questions, whether a candidate answer actually answers each one. You do not
need to know anything about Buddhism, Pali, or this project's code — you
just need to read English text and make a judgment call.

**The ask: `data/eval/annotation_v2_sample30.csv`, 208 rows across 30
questions, realistically 1-1.5 hours.** Each row is a short paragraph you
have to read and weigh (~115 words on average: the question, a story
summary, and a verse translation), not a quick yes/no glance, so please
budget real time for it rather than a coffee-break.

There is also a full sheet, `data/eval/annotation_v2_blank.csv` (507 rows,
72 questions, the 30-question file's superset) — **treat this as optional.**
At the same pace it's roughly 2.5-4 hours, a half-day task, and it's better
to do the 208-row file well, in one sitting with your full attention, than
to rush 507 rows or stop halfway through out of fatigue. If you do want to
attempt the full sheet, it's fine to split it across two sittings, or to
just do as much as you have time for — see "Returning the file" below for
how a partial sheet is handled.

**If you were sent a link to the web form, use that instead of the CSV.**
It shows the same 208 rows, saves each judgement as you make it (you can
stop and come back), keeps your answers private from other readers, and
lets you download your sheet as the same CSV. The rule and the advice below
apply unchanged.

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

Open `data/eval/annotation_v2_sample30.csv` (or, if you're doing the
optional full set, `data/eval/annotation_v2_blank.csv`) in a spreadsheet
program (Excel, Google Sheets, LibreOffice Calc — anything that opens CSV).
It has one row per (question, candidate story) pair. Columns:

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
- Don't reorder or delete rows, and don't rename the file's columns.
- If you're genuinely unsure on a row, pick your best judgment and say why
  in `comment` rather than agonizing over it — a single uncertain call
  doesn't affect much.

**If you run out of time partway through, send back what you have.** Rows
you haven't gotten to yet should just stay blank — leave `relevant` empty
rather than guessing to fill the cell. The processing script scores
whatever's filled in and reports how many rows were still blank, so a
half-finished sheet is still useful; it is not treated as a failed
submission. (The only thing that *is* a problem is a stray value that
isn't `0`, `1`, or blank — e.g. typing "y" — since that looks like a
formatting mistake rather than an unanswered row.)

## Returning the file

Save your filled-in copy under a new name (e.g.
`annotation_v2_filled_<yourname>.csv`) so the blank template isn't
overwritten, keep it as CSV (not `.xlsx`), and send it back the way you
were asked to — whether or not you finished every row. Someone on the
project will then run it through
`python -m dhammapada_rag.eval.annotation_sheet kappa <your file>`, which
compares your judgments against the first judge's and reports Cohen's
kappa (a standard agreement statistic) plus a list of every row where you
two disagreed, for review — not to grade you, but to find questions that
are genuinely ambiguous versus ones with a clear right answer.
