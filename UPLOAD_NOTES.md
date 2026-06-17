# Zenodo upload — contents & notes

The `zenodo/` folder holds the **anonymized reproducibility artifact** for double-anonymous
review as **two files** — **`README.md`** and **`artifact.zip`** — which you upload to the
anonymized repository link now (for review) and to Zenodo with a DOI on acceptance. This notes
file lives at the project level and is **not** part of the upload.

## Contents of `zenodo/` — upload BOTH files
- `README.md`    — reproduction guide (author names anonymized); kept loose so Zenodo shows it as the landing page.
- `artifact.zip` — everything else, bundled (`unzip` → `code/ data/ figures/ paper/` + a copy of the README):
  - `code/`    — benchmark harness (`run.py`, engines, `payloads.py`, `report.py`, `docker-compose.yml`, `tests/`); excludes `.venv/`/`__pycache__/`.
  - `data/`    — raw per-run + summary CSVs, `emissions.csv` (geolocation scrubbed), `threeway_summary.csv`, `skipped.csv`.
  - `figures/` — the six figure PDFs (metadata stripped).
  - `paper/`   — anonymized LaTeX source (`main.tex`, `references.bib`, `sn-jnl.cls`, `sn-basic.bst`) + compiled anonymized `main.pdf` (metadata stripped).

## Anonymization applied (double-anonymous)
- `paper/main.tex`: author/affiliation/email, acknowledgements, funding, and the declarations block removed; pinpoint province name dropped (country retained for the grid factor); self-references neutralised.
- `data/emissions.csv`: `region`, `longitude`, `latitude` blanked (kept `country=Indonesia` and `cpu_model`, which the paper already discloses).
- `figures/*.pdf` and `paper/main.pdf`: PDF metadata (creator/producer/timestamp + XMP) stripped.
- `README.md`: "How to cite" author names → "[Authors hidden for double-anonymous review]".

## Keep OUT of the anonymized upload (these identify the authors)
- `CONTEXT.md` (roadmap), this `UPLOAD_NOTES.md`, and `declarations/` (real names — submission-form only).
- The two **ATIGB conference papers** (`../postgre-vs-mongodb-carbon-footprint/.../alfa_yohannis_3.tex` and `../postgre-vs-postgre-minio-carbon-footprint/.../alfa_yohannis_4.tex`, and their PDFs). They name the authors, so they must **not** go in `zenodo/` or in `main.tex`. Instead, disclose them to the **editor only**: cover letter + the "Dual publication" declaration (`declarations/dual_publication.txt`) + upload as **Related Files** in Editorial Manager.
- `code/.venv/` and build artifacts (`*.aux`/`.log`/`.synctex.gz`/…).

## Before uploading
- [ ] **Upload exactly two files:** `README.md` (loose) and `artifact.zip`.
- [ ] Pick a **LICENSE** in Zenodo's metadata form (or drop a `LICENSE` file inside `artifact.zip` before zipping) — e.g. code MIT + data/figures CC-BY-4.0.
- [ ] Inside the zip, `code/assets/` is empty: add the Durdle Door / Pexels source photo if full payload regeneration is needed (the paper cites it).
- [ ] On **acceptance**: swap in the non-anonymized `main.tex`/`README.md`, restore funder/region if desired, **re-zip**, then mint the Zenodo DOI and add it to the paper's Data/Code Availability.
