# Revision plan — ESD desk review (review01)

**Manuscript:** *Carbon Footprint and Carbon-Aware Selection of Document-Oriented, Relational, and
Hybrid Object-Relational Storage for Image-Based Time-Series Workloads in Green IoT*
**Journal:** Environment Systems and Decisions (Springer)
**Editor:** Otavio Jose de Oliveira
**Submission ID:** `35174617-3240-44d6-bb1c-fcc74ec1cd4f`
**Support contact:** vinothkumar.raji@springernature.com
**Plan drafted:** 2026-08-14

## Status of the submission

This is an **editor-level desk revision**, not peer review. The manuscript has *not* yet reached an
Associate Editor. The editor's assessment is positive on scope, methodology, and reproducibility, and
explicitly credits the paper for going beyond a conventional performance benchmark. Five issues must
be resolved before it is passed on.

No new science is required. All five items are addressable by rewriting, re-citing, and one
supplementary validation run.

## Decisions taken

| Question | Decision |
|---|---|
| Were AI tools used? | **Yes — language/editing only.** Declare tool, state authors reviewed all content and take full responsibility. |
| Depth of generalizability evidence | **Analytical model + real-deployment case study.** Upgraded 2026-08-14: the empirical layer is now an operational face-recognition attendance system (IP cams + webcams) on different hardware, not a generic second laptop. See Item 3c. |
| Resubmit or change journal? | **Resubmit to ESD.** The editor affirmed scope fit, methodology, and contribution in writing, and invited revision. All five points are presentation, not science. Switching restarts a 6–10 week queue, forfeits a confirmed scope match in a journal that publishes little ICT work, and would attract the same two criticisms from reviewers later. |
| Extension | **To 19 August 2026.** Author's internal target is 19 Aug 08:00 WIB; the email states the date only, which in UTC terms grants until 06:59 WIB on 20 Aug — a free ~23-hour buffer. Reason given honestly: the notification went to an address not monitored daily, under a changed SNAPP subject line. |

---

## Item 1 — Position the framework in the literature

> "The discussion should better position the proposed framework within the existing scientific
> literature, demonstrating more convincingly how it advances beyond previous studies rather than
> primarily summarizing the experimental findings."

**Current state — the editor is factually right, and it is measurable.**
The entire Discussion section (`paper/main.tex:438-448`) cites **five sources, every one of them
vendor or technical documentation**: Snappy, a Percona blog post, the PostgreSQL TOAST docs, the
WiredTiger architecture docs, and the Pexels source image. **Not one scholarly citation.** All the
literature sits in §2 Related Work and is never revisited, so the Discussion reads exactly as the
editor describes: mechanism explanation followed by threats to validity.

**Planned fix**

1. New Discussion subsection **"Positioning against prior work"**, placed before *Threats to validity*:
   - What TSBS, the CrateDB benchmark, and Diva et al. actually *concluded*, and why those conclusions
     do not transfer once payloads reach multiple megabytes — the paper's crossover result overturns
     "MongoDB ingests faster" as a resolution-independent claim.
   - Green Algorithms, SCI (ISO/IEC 21031:2024), and *Chasing Carbon* supply carbon-accounting
     **methods** but stop short of per-operation database carbon; state precisely what this work adds
     on top of each.
   - Name the delta explicitly: first per-*(engine × operation × resolution)* **directly measured**
     carbon for binary time-series storage, versus estimation-by-apportionment in earlier work.
2. Extend Table 1 (`tab:relwork`) with a **"What it concludes / what this work changes"** column, so
   the advance is visible in the table rather than asserted in prose.

---

## Item 2 — Dialogue with recent ESD publications

> "The manuscript would also benefit from a stronger dialogue with recent publications in Environment
> Systems and Decisions, reinforcing its contribution to the journal's body of knowledge."

**Current state.** `paper/references.bib` holds 42 entries and **zero from ESD**. There is a comment
block at line 280 labelled *"Peer-reviewed environmental / sustainable-computing anchors (added for
ESD)"* — but those entries are Science, ACM SIGENERGY, and Environmental Pollution. The journal's own
literature is entirely absent. This is the cheapest item to fix and the one most likely to be checked
directly by the editor.

**Journal scope, for framing** (from ESD aims and scope): the journal covers *"interrelated social,
technological, environmental, and economic systems with attention to performance, risk, costs,
sustainability, and resilience"*, featuring *"decision analysis, systems engineering, risk assessment
and risk management, resilience analysis, policy analysis, data science, and communication."*
The paper should therefore be framed as **decision analysis over a socio-technical system**, not as a
database benchmark — the existing "environmental-systems decision" framing in the Introduction is the
right hook and should be strengthened and tied to cited ESD work.

**Planned fix.** Locate and cite 5–8 recent (2020–2026) ESD articles across decision frameworks under
environmental constraints, ICT/digitalisation sustainability, and LCA-informed decision support.
Place them in three locations, **engaged rather than name-dropped**:

- Introduction — the environmental-systems-decision framing.
- Related Work — a new paragraph on decision frameworks in the ESD tradition.
- Discussion — how this framework complements ESD's decision-analysis methods.

> ⚠️ **Open — citations not yet sourced.** Initial searches returned journal-level metadata and
> Springer papers from *other* journals, not ESD articles. Specific ESD papers must be identified and
> verified before drafting. **No citation will be written that has not been confirmed to exist.**

---

## Item 3 — Generalizability of the decision framework

> "The framework is derived almost entirely from the experimental environment developed by the
> authors, and its applicability beyond the evaluated hardware, software configuration, and workload
> characteristics remains insufficiently discussed."

**Current state.** Generalizability is defended by *argument only*: the "controlled baseline"
paragraph (`paper/main.tex:128`) and the threats-to-validity passage, which repeatedly assert the
ordering "is expected to" transfer. The editor is asking for **evidence**, not assertion.

**Planned fix — three layers.**

**3a. Analytical.** Derive a cost model of the form

> carbon ≈ *fixed per-operation overhead* + *per-byte payload-handling cost*

and show the crossover occurs where the hybrid's fixed HTTP round-trip cost is amortised by its lower
per-byte cost. This turns a point observation on one machine into a **formula a reader instantiates
with their own hardware constants** — the single highest-value change for this item.

**3b. Structural vs. measured.** Separate, throughout §6 (framework) and the Discussion:

- **Structural / hardware-independent** — the 16 MB BSON bucketing ceiling is a protocol limit and
  provably general; the inline-versus-externalised mechanism is generic across engines.
- **Host-specific** — absolute mg CO₂eq, exact crossover resolutions, amplification factors.

Claims currently blur these two, which is what makes the framework look setup-bound.

**3c. Empirical — real-deployment case study (decision made 2026-08-14).**

Instead of a generic second laptop running the same synthetic collages, use the author's **operational
face-recognition attendance system** (IP cameras + webcams) as a case study on **different hardware**.
This is a strictly stronger answer, because the editor named three dimensions of concern and a second
laptop would only address one:

| Editor's concern | Second laptop | Attendance system |
|---|---|---|
| "evaluated **hardware**" | ✅ different CPU | ✅ different CPU |
| "**software configuration**" | ❌ identical stack | ✅ production stack |
| "**workload characteristics**" | ❌ same synthetic collages | ✅ real cameras, real capture rates |
| "**practical value**… demonstrated more convincingly" | ❌ still a benchmark | ✅ a system that actually exists |

**Three deliverables, in priority order** (highest value per unit of effort first):

1. **Framework application (analysis only — no new measurement).** Characterise the deployment:
   camera count, native capture resolution, frame rate, retention period. Push those parameters
   through the decision framework (Table 5) and the measured per-frame carbon rates to produce a
   concrete recommendation and an annual footprint for a **real** installation. This alone converts
   the fleet-scale projection from an illustrative normaliser into a grounded case, and it is
   achievable within the one-week window regardless of hardware access.
2. **Real-payload validation.** Replace the Durdle Door collage with **actual captured frames** from
   the IP cam and webcam. Directly retires the "single image corpus / single coastal scene" limitation
   admitted in threats-to-validity, and tests whether real face-capture entropy shifts the
   amplification and crossover figures.
3. **Second-hardware subset run.** Execute the benchmark protocol on the attendance-system host across
   360p, 1080p, 4K, 6K — both sides of the crossover — and report whether the architectural ordering
   is preserved. Add the second environment as a column in Table 2 (`tab:env`).

> ⏱ **One week is tight for all three.** Deliverable 1 is safe. Deliverable 2 is likely. Deliverable 3
> depends entirely on how quickly the benchmark can be run on that host without disrupting a
> **production** attendance system — which must not be destabilised for a paper. If time runs short,
> ship 1 + 2 and describe 3 as ongoing; the case study carries point 3 on its own.

> ⚠️ **Anonymisation risk — the case study is the biggest exposure in this revision.** A named
> institution, campus, building, staff photographs, or an identifiable deployment de-anonymises the
> authors instantly. Describe it generically: *"an operational attendance system at a higher-education
> institution."* Never include captured face images in the manuscript or artifact — that is both a
> de-anonymisation risk and a personal-data issue.

> ⚠️ **Ethics/GDPR.** Face recognition on real people means biometric personal data. Even though the
> paper measures *storage carbon* and not identities, the manuscript should state that no personal
> data was retained, that images were used only for payload characterisation, and whatever consent or
> institutional approval covers the deployment. Expect an Associate Editor to ask. The current
> declarations say nothing about ethics — this now needs a real answer rather than "not applicable".

---

## Item 4 — Abstract must acknowledge limitations

> "The abstract should also explicitly acknowledge the main limitations of the research."

**Current state.** The abstract (`paper/main.tex:72`) contains **no limitation language at all**.

**Planned fix.** Add 1–2 sentences near the end covering:

- single-host, single-client **controlled baseline** (not a distributed/multi-client deployment);
- a single image corpus (one high-entropy photographic scene);
- the Indonesian grid factor — noting that *ranking* is grid-invariant since emissions scale linearly
  with grid intensity;
- embodied-carbon and fleet-scale numbers are **first-order estimates**.

The abstract is already long, so trim the fleet-scale clause to make room and hold the word count.

---

## Item 5 — AI-use declaration

> "If artificial intelligence tools were used for language polishing or translation, this should be
> transparently declared in accordance with the journal's editorial policies."

**Current state.** *Statements and Declarations* (`paper/main.tex:459-461`) contains **only Funding** —
no AI declaration, no competing interests, no data availability, no author contributions.

> ✅ **Resolved:** the working copy had a duplicated `\textbf{Funding.} \textbf{Funding.}` at line 461.
> Comparison against `upload/paper/main.tex` (the actual v1.1 upload) confirmed the **submitted file was
> clean** — the duplication was a local regression introduced after upload. The editor never saw it, so
> it needs no mention in the response letter. Fixed in the working copy on 2026-08-14.

**Planned fix.** Rewrite the section to include:

| Declaration | Content |
|---|---|
| **Use of AI-assisted technologies** | Declare AI used for **language/editing only**; name the tool; state authors reviewed and edited all output and take full responsibility for the content. AI is not credited as an author. |
| **Funding** | Fix the duplicated heading. Retain "no funding received". |
| **Competing Interests** | Required by Springer — add. |
| **Data Availability** | Point to the public artifact (code, Docker configs, raw CSVs, Zenodo deposit). |
| **Author Contributions** | Required by Springer — add (post-anonymisation). |
| **Ethics approval** | State not applicable — no human or animal subjects. |

---

## Deliverables

1. Revised `paper/main.tex` (all five items).
2. Updated `paper/references.bib` (ESD entries + any positioning references).
3. Second-machine results merged into `data/` and Table 2.
4. **Point-by-point response letter** mapping each of the editor's five requests to the specific
   changes, with section and line references.
5. Rebuilt `main.pdf`, verified for broken citations and overfull boxes.

## Open blockers

| # | Blocker | Needed from author |
|---|---|---|
| 1 | Specific recent ESD papers not yet identified | Nothing — being searched now; will be verified before citing |
| 2 | Second validation host | Which machine is available (CPU, OS, RAPL support)? |
| 3 | AI tool name for the declaration | Which tool was used for language editing? |
| 4 | Author contributions | Cannot be drafted until de-anonymisation at acceptance |

## Notes

- The double-blind anonymisation must be preserved in all new text — the two existing
  `[hidden for double-blind review]` self-citations are handled correctly and new ESD citations must
  not de-anonymise the authors.
- Turnaround should be tight: a desk revision that stalls risks being treated as a withdrawal.
