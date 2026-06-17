# Declarations — ready-to-paste text for the ESD submission system

*Environment Systems and Decisions* uses **double-anonymous** review and collects these
statements in the **submission form** (Editorial Manager), **not** in the manuscript. The
manuscript (`../paper/main.tex`) therefore no longer contains them. Paste each file's
contents into the matching form field.

| ESD form field | File |
|---|---|
| Research funding | `funding.txt` |
| Competing interests (choose "No") | `competing_interests.txt` |
| Data availability | `data_availability.txt` |
| Code availability (fold into data-availability if one field) | `code_availability.txt` |
| Author Contributions Statement | `author_contributions.txt` |
| Acknowledgements | `acknowledgements.txt` |
| Generative-AI use disclosure | `ai_use_disclosure.txt` |
| Dual publication (choose "Yes") | `dual_publication.txt` |
| Ethics / consent | `ethics_and_consent.txt` |

These fields are collected separately and are **not shown to reviewers**, so real names,
affiliations, and funders are fine here (unlike in the manuscript).

> ⚠️ **Before submitting**
> - `data_availability.txt`: anonymized review link **added** (Zenodo draft preview). ⚠️ Also verify the Zenodo **record metadata** (Creators/Authors, Title, Description) shows **no real names** — the preview page reveals them even though the files inside are clean.
> - `author_contributions.txt`: confirm the A.Y./A.W. split matches reality.
> - **Dual publication / Related Files:** select "Yes" for dual publication (see
>   `dual_publication.txt`) and upload the two ATIGB conference papers (companion work) as
>   **Related Files** in Editorial Manager. They are editor-facing only — keep them out of the
>   manuscript and the Zenodo artifact.
> - This `declarations/` folder is for the **form only** — do **not** upload it with the
>   anonymized manuscript or the Zenodo artifact (it contains identifying information).
