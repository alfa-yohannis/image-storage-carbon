# Revision upload — what goes in which slot

Submission `35174617-3240-44d6-bb1c-fcc74ec1cd4f`, revision of v1.1.

Rebuild everything here with:

```bash
bash submission/make_paper_zip.sh     # -> paper.zip, and proves it compiles
```

The PDFs are copied from `../paper/` and `../reviews/` by hand; both are produced by
`latexmk` in their own folders.

## Portal slots

| Slot | File | Notes |
|---|---|---|
| **Manuscript file** | `paper.zip` | LaTeX source, *not* a PDF. The portal compiles it. Clean — no highlights, no tracked changes. |
| **Point-by-point response** | `response-letter-01.pdf` | Anonymised, 7 pp. Required to be a PDF. |
| **Related file** | `main-marked.pdf` | Optional. Green text is new or rewritten this revision. Never upload this as the manuscript. |
| **Related files** | the two ATIGB conference papers | Editor-facing only, per the dual-publication answer. See `../declarations/dual_publication.txt`. |

Form fields are filled from `../declarations/*.txt`. Those are collected separately and are
**not** shown to reviewers, so the real names in them are correct there. Do not upload the
`declarations/` folder itself, and do not put it in the Zenodo deposit.

## Why `paper.zip` is laid out the way it is

It mirrors `../upload/paper.zip`, the archive that passed the technical check for v1.1:
everything under a top-level `paper/` folder, `figures/` beside `main.tex`, and no PDF of the
manuscript. `main.tex` sets `\graphicspath{{figures/}{../figures/}}`, so the nested `figures/`
resolves. `main.bbl` is included so the bibliography resolves even if the compiler does not run
bibtex.

`make_paper_zip.sh` extracts the finished archive into a temporary directory and compiles it
there with nothing else on the path, because a zip that builds here but not on their machine is
worse than no zip at all.

## Before pressing submit

- [ ] Zenodo record updated to artifact **v2.0** (four archives, see `../zenodo/`), and the
      record's **Creators / Title / Description** checked for real names — the preview page shows
      them even when the files inside are clean.
- [ ] Anonymised Zenodo preview link current in `../declarations/data_availability.txt`.
- [ ] `../declarations/author_contributions.txt` — the A.Y./A.W. split confirmed.
- [ ] `../declarations/dual_publication.txt` — conference title, edition, year, dates confirmed.
- [ ] The AI-use declaration read and agreed: it now covers code assistance as well as language
      editing, so that the manuscript and the form field say the same thing.
- [ ] Uploaded by the **original submitting author** (the gmail account), which may differ from
      the corresponding author.
