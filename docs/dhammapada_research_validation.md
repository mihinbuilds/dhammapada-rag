# Research validation set

Distinct from `dhammapada_probe_set.md`, which catches regressions. These
questions exist to answer one thing a reviewer will ask: **what can this system
do that a simpler one cannot?**

Each question names the baseline it should defeat. Run every question under
every condition and report the result as a table — that table is the core
evidence of your paper, more so than any aggregate metric.

## Conditions to run

| Condition | What it tests |
|---|---|
| `no_retrieval` | the generator alone, no context — the honest floor |
| `verse_only` | verse chunks only |
| `commentary_only` | story chunks only |
| `flat` | full index, no parent-group assembly |
| `full` | the complete system |

**`no_retrieval` is the condition most papers omit and reviewers ask about
first.** If Qwen2.5-7B answers a question correctly with no context, retrieval
contributed nothing there, and you should know which questions those are.

---

## A. Defeats `no_retrieval` — corpus-specific facts

A generator without your corpus cannot know these, because they concern *your
edition's* apparatus rather than general Buddhist knowledge.

1. How many verses does story 17.8 cover, and which are they?
2. What does Ānandajoti's 2024 edition title the story for Dhp 114, and what did Burlingame call it?
3. What is the nidāna of the story attached to Dhp 221 — where was it spoken?
4. Which stories in your corpus are set at Jetavana?
5. How many distinct commentarial stories cover the 423 verses?

**Watch for:** a plain LLM will confabulate plausible titles and locations. If
`no_retrieval` produces confident wrong answers while `full` produces cited
correct ones, that contrast is a figure in the paper.

---

## B. Defeats `verse_only` — commentary-dependent

The verse alone cannot answer these. This is your central architectural claim.

6. To whom was Dhp 1 spoken, and what happened to him?
7. What did the Buddha ask Kisā Gotamī to bring, and why could she not bring it?
8. What did Rohinī's questioner learn at the end of the teaching?
9. Which story involves a bhikkhu felling a tree and injuring a devatā's child?
10. What occasioned the verse about the swerving chariot?

**Watch for:** under `verse_only` the system should say the commentary is
unavailable, not manufacture an occasion. A `verse_only` run that confabulates a
story is itself a finding — the model filling a retrieval gap from memory.

---

## C. Defeats `commentary_only` — verse-dependent

11. What is the Pali of Dhp 223?
12. Which verses in the Kodhavagga use a chariot image?
13. Does Dhp 166 contain the word *nibbāna*?
14. Quote the Pali pāda in Dhp 1 that contains *manopubbaṅgamā*.

Q13 is the sharp one. The answer is **no** — Dhp 166 has *sadattha*; the
identification with nibbāna is Buddhaghosa's gloss. A system that answers "yes"
has collapsed the layers, which is the failure the whole project exists to
prevent.

---

## D. Defeats `flat` — requires parent-group assembly

Each retrieves on one small unit and needs the whole group returned.

15. Give me Dhp 114 with its Pali, an English translation, and the story that explains it.
16. I remember a story about a mustard seed — what verse does it belong to and what does that verse say?
17. Show me everything your corpus holds for Dhp 3.

Q16 is the "retrieve small, return whole" demonstration: it matches on a
narrative detail and must return the verse layer.

---

## E. Alignment table — your unique artifact

No other Dhammapada tool answers these.

18. Is Dhp 4 explained on its own or together with another verse?
19. Are Dhp 1 and Dhp 2 explained by the same story?
20. Which single story explains Dhp 320, 321, and 322?
21. Which verse group in the corpus is the largest?
22. Are there verses explained by more than one story?
23. Do your sources disagree about any verse grouping? Name one.

Q23 only works once the corpus rebuild has a second witness for grouping. It is
worth building toward — "editions disagree here, and here is how" is a
capability nothing else has.

---

## F. Layer discrimination — the philological core

Each has a popularly-known answer that comes from the commentary. A correct
response attributes it correctly and does not present it as the verse's content.

24. Does the Dhammapada say the goal of life is nibbāna?
25. Is Dhp 1 about a blind monk?
26. Does the mustard seed appear in the verse or in the commentary?
27. Dhp 153–154 mentions a house-builder. Does the text say who that is, or is that an interpretation?
28. What does the Dhammapada say about anger — and which of that is the verse and which the commentary?

Q27 is the subtlest: Dhp 154 names *taṇhā* directly, so "verse" is the correct
attribution. It tests over-attribution to commentary, the failure induced by
your own coverage instruction.

---

## G. Boundary and refusal

29. Which verse mentions the internet?
30. What does Dhp 500 say?
31. Summarize the entire Dhammapada in one sentence.
32. What is the Dhammapada's position on democracy?

Q31 should produce a synthesis claim acknowledging that a 423-verse anthology
across 26 vaggas resists one sentence, not a confident aphorism.

---

## H. Consistency

33. Ask Q7 three times with the same seed — are the answers identical?
34. Ask "who was Kisā Gotamī?" and "tell me about the woman who lost her child" — do shared claims carry the same layer tags?
35. Ask Q6 at `top_k` = 1, 3, and 5 — does the answer stay stable, or does extra context change what is claimed?

Q35 is rarely reported and reviewers like it: sensitivity to a retrieval
hyperparameter is a robustness result.

---

## Reporting

One table, questions as rows, conditions as columns, cells scored
correct / partial / wrong / confabulated. `confabulated` deserves its own
category — a confident wrong answer is worse than an admitted gap, and the
distinction is exactly what a faith-adjacent tool must get right.

Then two summary rows: how many questions `full` answers that `no_retrieval`
cannot, and how many that `verse_only` cannot. Those two numbers are your
contribution stated quantitatively.

---

# What the committee will ask *you*

Prepare these. They are harder than anything above and they are what actually
gets asked.

1. **How is this different from full-text search over a PDF?** — The honest
   answer is layer attribution and the alignment table, not the chatbot. Say so.
2. **How do you know the commentary layer adds value rather than just more
   text?** — Your `verse_only` ablation, broken out by query type, with the
   narrative row's near-mechanical collapse acknowledged rather than claimed.
3. **Buddhaghosa's authority is contested. Does your system take a position?**
   — It surfaces and attributes; it does not adjudicate. Have the ethics
   section ready.
4. **Who verified the alignment table?** — Currently: one person, no second
   witness. Do not overstate this.
5. **Your judgments were produced by the same AI that generated the outputs.
   Why should I trust any number?** — The hardest question. A second annotator
   and a κ statistic is the only real answer; without it, foreground the
   limitation before they raise it.
6. **Why Ānandajoti rather than PTS?** — Licensing, and say so plainly.
   Copyright is a legitimate scholarly constraint.
7. **What does failure look like?** — You have four documented fidelity errors
   that passed every structural check. Lead with them. Candour about failure is
   the strongest credibility signal available to you.
8. **What would a scholar use this for that they cannot already do?** — Have a
   concrete answer. "Find every verse whose commentary is set at Jetavana" and
   "show where editions disagree on verse grouping" are real answers. "Ask
   questions about the Dhammapada" is not.

Question 8 is the one to work out first. If you cannot answer it in one
sentence, the paper's framing needs work before the system does.
