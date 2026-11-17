# Revision upload — what goes in which slot

Submission `35174617-3240-44d6-bb1c-fcc74ec1cd4f`, revision requested on 3 November 2026 after
peer review (two reviewer reports and an editor's comment).

Rebuild everything here with:

```bash
python3 paper/make_marked.py                                              # -> paper/main-marked.tex
bash submission/make_paper_zip.sh                                         # -> paper.zip, and proves it compiles
python3 zenodo/make_artifact.py --version 2.1 --no-frames --supplementary # -> supplementary_files.zip
```

Build `paper/main.tex` first: `paper.zip` and the artifact both need `paper/main.bbl`. The Online
Resources (`paper/esm/ESM_1.tex`, `ESM_2.tex`) are built after it, because they take their section
and table numbers from `main.aux`. `make_marked.py` diffs against the version the reviewers read
(commit `8631822`, v1.1 of 19 August 2026), not against the original June submission.

Strip the metadata from every PDF before uploading it: the journal is double-anonymous, and the
portal asks for all final files' metadata to be anonymised.

## Portal slots

| Slot | File | Notes |
|---|---|---|
| **Point-by-point response** | the response letter, as a PDF | Anonymised. It is kept outside this repository. |
| **Manuscript file** | `paper.zip` | LaTeX source, *not* a PDF. The portal compiles it. Clean: no highlights, no tracked changes. |
| **Supplementary files** | `ESM_1.pdf`, `ESM_2.pdf` | Online Resources 1 and 2, cited in the manuscript under those names. |
| **Supplementary files** | `supplementary_files.zip` | The reproducibility artifact, minus the recorded frames. Same content as the Zenodo main archive. |
| **Related file** | `main-marked.pdf` | Optional. Green text is new or rewritten since the reviewed version. Never upload this as the manuscript. |

The two ATIGB conference papers were uploaded as editor-facing related files with the original
submission (see `../declarations/dual_publication.txt`) and have not changed.

Form fields are filled from `../declarations/*.txt`. Those are collected separately and are
**not** shown to reviewers, so the real names in them are correct there. Do not upload the
`declarations/` folder itself, and do not put it in the Zenodo deposit.

## Why `supplementary_files.zip` is built from the deposit staging

The v1.0 pair drifted: `upload/supplementary_files.zip` and `zenodo/artifact.zip` were meant to be
the same package, and by June they were not, the supplementary copy carrying an older `main.tex`.
Both are now written from one staging tree in `make_artifact.py`, in the same invocation, so they
cannot disagree. The only difference is the filename.

## Why `paper.zip` is laid out the way it is

It mirrors the archive that passed the technical check for v1.1: everything under a top-level
`paper/` folder, `figures/` beside `main.tex`, and no PDF of the manuscript. `main.tex` sets
`\graphicspath{{figures/}{../figures/}}`, so the nested `figures/` resolves. Only the figures
`main.tex` includes go in; the rest belong to the Online Resources. `main.bbl` is included so the
bibliography resolves even if the compiler does not run bibtex.

`make_paper_zip.sh` extracts the finished archive into a temporary directory and compiles it
there with nothing else on the path, because a zip that builds here but not on their machine is
worse than no zip at all.

## Before pressing submit

- [ ] The Zenodo draft carries artifact **v2.1** and the new `paper.zip` and
      `supplementary_files.zip`, and is **not** published: the anonymised preview link in
      `../declarations/data_availability.txt` points at the draft, and the deposit is due on
      acceptance.
- [ ] Every uploaded PDF has empty metadata (`pdfinfo` shows no title, author, creator, producer
      or dates).
- [ ] Uploaded by the **original submitting author** (the gmail account), which may differ from
      the corresponding author.
