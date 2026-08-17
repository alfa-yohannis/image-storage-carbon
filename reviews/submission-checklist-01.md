# Revision submission checklist — ESD (review01)

**Submission ID:** `35174617-3240-44d6-bb1c-fcc74ec1cd4f`
**Submission version:** v.1.1 · **Status:** With editor — action needed
**Support contact:** vinothkumar.raji@springernature.com
**Companion document:** [revision-plan-01.md](revision-plan-01.md) — what to change and why

---

## ⏱ Deadline: 35 minutes past, in UTC — effectively on time

**Recommended submission date: 13 Aug 2026.** Springer's systems record deadlines in **UTC**, so UTC is
the reference that matters — not WIB, and not European local time:

| Reference | Time when this was assessed |
|---|---|
| **UTC (Springer's clock)** | **14 Aug 2026, 00:35** — deadline passed **35 minutes** ago |
| London (Springer UK) | 14 Aug 2026, 01:35 BST |
| Heidelberg (Springer DE) | 14 Aug 2026, 02:35 CEST |
| Jakarta (author) | 14 Aug 2026, 07:35 WIB |

Taking the deadline as end-of-day 13 Aug UTC (23:59), it elapsed **35 minutes ago**. Not a day, not
overnight — **just over half an hour**, in the middle of the night across every Springer office.

This is **not an overdue submission in any meaningful sense**:

- the portal says *"We **recommend** submitting your revisions by…"* — a recommendation, not a cutoff;
- **Submit anonymised revision** is still live, so nothing has been closed;
- editorial staff open the inbox around 09:00 CEST — **~7 hours from now**, ≈14:00 WIB — so an email
  sent this morning is the **first thing they see on the 14th**.

**Take no apologetic tone.** Requesting an extension 35 minutes past a recommended date, before any
staff member has seen the file, is an ordinary same-day request. Apologising for lateness would
concede a problem that does not exist.

**Action: send the extension request this morning (WIB).** See
[extension-request-draft.md](extension-request-draft.md). What would create a genuine problem is
silence over several days — not 35 minutes.

**Consequence for the plan.** The second-machine validation run (editor point 3) needs wall-clock
benchmark time and cannot be completed today. Two options:

1. **Request the extension, keep the full plan** — recommended. The second-host evidence is the
   strongest answer to the generalizability criticism and is worth the extra weeks.
2. **Submit fast with the analytical layer only** — drop to the model-plus-reframing approach, which
   needs no new runs. Weaker on the editor's most substantive point.

> ⚠️ The editor's feedback was emailed to **alfa.ryano@gmail.com**, which differs from the SNAPP
> account address (alfa.ryano@pradita.ac.id). The gmail account is most likely the **original
> submitting author** — the one who must perform the upload. Confirm before revision day.

---

## Journal's stated submission requirements

Reproduced from the revision request:

> The original submitting author must upload an anonymised point-by-point response to the comments as
> a PDF file. This must include a description of any additional experiments that were carried out and
> a detailed rebuttal of any criticisms or requested revisions that you disagreed with.
>
> Any files (including the manuscript) that have changed based on the comments will also need to be
> uploaded again. Do not include tracked changes in your manuscript file. If you need to upload a
> marked-up version of the revised manuscript with the changes highlighted you can upload it on the
> related file section.
>
> Please note the original submitting author may be different from the corresponding author.
>
> If you need an extension, please contact us and include your submission ID.

---

## What this implies for our revision

### 1. The response letter must be **anonymised**

This is a double-blind submission, and the requirement applies to the response document as well as the
manuscript. Concretely:

- ❌ No author names, institution, city, or country in the response PDF.
- ❌ No "as we showed in our previous paper [our-citation]" — keep the existing
  `[hidden for double-blind review]` convention for the two self-citations.
- ⚠️ **Watch the second-machine experiment.** Describing the new host risks de-anonymising by
  affiliation (e.g. naming an institutional cluster or lab machine). Describe it by
  **specification only** — CPU model, core count, RAM, OS, RAPL availability — never by name, owner,
  or location.
- ⚠️ **Watch the artifact link.** A GitHub/Zenodo URL carrying the author's name or handle
  de-anonymises. Use an anonymised deposit for review, or state that the artifact will be released on
  acceptance.
- ⚠️ **Strip PDF metadata** from the response PDF and any regenerated figure PDFs — the LaTeX
  toolchain embeds author/username fields. Use the project's existing PyMuPDF metadata-stripping step.

### 2. Must describe **additional experiments**

We committed to the second-machine validation run (editor point 3). The response letter must contain a
dedicated section describing it: hardware specification, which resolutions were re-run, the protocol
(identical to the original), and the result — specifically whether the architectural ordering was
preserved. This is the direct evidentiary answer to the generalizability criticism, so it should be
prominent rather than buried.

### 3. Must include a **rebuttal of anything we disagree with**

Silent non-compliance reads as an oversight; a reasoned rebuttal is explicitly invited. Candidate
points where partial pushback is legitimate and should be argued rather than quietly ignored:

| Point | Position |
|---|---|
| Generalizability | **Partial rebuttal.** We add real evidence (analytical model + second host), but should argue that the single-host controlled baseline is a *deliberate methodological choice* that isolates payload handling from scheduling and contention confounds — and that the 16 MB BSON ceiling is a protocol-level limit, general by construction rather than by measurement. |
| Everything else | **Full compliance.** Positioning, ESD dialogue, abstract limitations, and AI declaration are all accepted without argument — no rebuttal needed. |

### 4. Manuscript file: **no tracked changes**

- Submit a **clean** `main.pdf` compiled from `main.tex`.
- Do **not** use `\color`, `\hl`, `changes.sty`, or similar markup in the submitted file.
- For the optional highlighted version, generate it separately with `latexdiff` and upload it under
  **related files**, never in place of the clean manuscript:

  ```bash
  cd paper
  latexdiff main-ORIGINAL.tex main.tex > main-diff.tex
  latexmk -pdf main-diff.tex
  ```

  ✅ **The baseline already exists.** `upload/paper/main.tex` is the actual v1.1 file that was
  uploaded — verified byte-for-byte against the working copy, differing only by a duplicated
  `\textbf{Funding.}` that was a post-upload local regression (now fixed). Use it directly:

  ```bash
  cd 01_environment_systems_and_decisions
  latexdiff upload/paper/main.tex paper/main.tex > paper/main-diff.tex
  cd paper && latexmk -pdf main-diff.tex
  ```

  Do **not** overwrite `upload/` — it is the immutable record of what was submitted.

### 5. The uploader must be the **original submitting author**

The person who created the original submission must be the one to upload the revision — this may not
be the corresponding author. Confirm who originally submitted before revision day; a mismatch here
causes a rejected upload and a wasted deadline.

### 6. Extension

If the work (particularly the second-machine run) will not land in time, request an extension **early**,
quoting submission ID `35174617-3240-44d6-bb1c-fcc74ec1cd4f`. Requesting ahead of the deadline is
routine; missing it silently risks the submission being treated as withdrawn.

---

## Pre-flight

- [x] **Pristine submitted source archived** — `upload/paper/main.tex` is the as-submitted v1.1 file.
      No separate archive needed; treat `upload/` as read-only.
- [x] **Working copy reconciled** — the duplicated `\textbf{Funding.}` regression was fixed on
      2026-08-14, bringing `paper/main.tex` back in line with what was submitted.
- [ ] Identify and confirm the original submitting author (likely the gmail account).
- [ ] Send the extension request — see [extension-request-draft.md](extension-request-draft.md).

## Anonymisation note

`paper/main.tex` **is already the anonymised version** — author, affiliation, and email are
`[Hidden for Double-blind Review]`, and the two self-citations use the
`[hidden for double-blind review]` convention. New text must preserve this. Per `UPLOAD_NOTES.md`, the
declarations block was stripped for the Zenodo artifact copy, but that does **not** apply to the
manuscript: an AI-use declaration, funding "none", competing interests, and data availability are all
**non-identifying** and should appear in the submitted manuscript. Only *Author Contributions* must
wait for de-anonymisation at acceptance.

## Files to upload

| File | Format | Notes |
|---|---|---|
| Point-by-point response | **PDF** | Anonymised. Includes additional-experiments description + rebuttal. |
| Revised manuscript | PDF (+ source per journal rules) | **Clean — no tracked changes.** |
| Marked-up manuscript | PDF | *Optional*, "related files" section only. `latexdiff` output. |
| Figures | PDF (vector) | Re-upload only if regenerated; strip metadata. |
| Artifact / data statement | — | Anonymised link or "available on acceptance". |

## Final checks before upload

- [ ] Response PDF contains no author, institution, or location identifiers.
- [ ] PDF metadata stripped from response and any regenerated figures.
- [ ] Manuscript compiles clean — no broken citations, no `??` references.
- [ ] Every one of the editor's five points has a numbered reply with section/line references.
- [ ] Additional experiment (second host) described with specification, not identity.
- [ ] AI-assisted technology declaration present and truthful (language/editing only).
- [ ] Duplicated `\textbf{Funding.}` typo fixed.
- [ ] Clean manuscript uploaded as the manuscript; marked-up version only under related files.
- [ ] Uploaded by the original submitting author.
