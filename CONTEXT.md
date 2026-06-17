# Paper B — Target: *Environment Systems and Decisions* (Springer)

Roadmap & to-do untuk mengembangkan **paper carbon footprint** (Paper B, track Green)
menjadi artikel jurnal **Q2** yang menyasar *Environment Systems and Decisions* (ESD).

> **Konsep paper:** konsolidasi dua draf konferensi
> [`alfa_yohannis_3.tex`](../postgre-vs-mongodb-carbon-footprint/paper/alfa_yohannis_3.tex)
> (+) [`alfa_yohannis_4.tex`](../postgre-vs-postgre-minio-carbon-footprint/paper/alfa_yohannis_4.tex)
> menjadi **satu** studi *three-way*: **MongoDB vs PostgreSQL-BYTEA vs PostgreSQL+MinIO**,
> dibingkai sebagai **penilaian & pengambilan keputusan carbon untuk infrastruktur IoT hijau**.

---

## 📌 Fakta jurnal (verifikasi ulang sebelum submit)

| Item | Nilai |
|---|---|
| Penerbit | Springer Nature |
| Quartile | **Q2** (SJR ≈ 0.59) |
| ISSN | 2194-5403 / 2194-5411 |
| Model | **Hybrid** → publikasi **gratis** via jalur subscription; OA berbayar (opsional) |
| Biaya penulis | **Rp0** (jalur non-OA) — lihat [Strategi biaya & OA](#-strategi-biaya--open-access) |
| Scope | environmental systems, **risk analysis**, **life-cycle assessment (LCA)**, **decision analysis**, infrastructure & sustainability decisions |

- [ ] Verifikasi *Aims & Scope* terbaru di https://link.springer.com/journal/10669
- [ ] Verifikasi *Submission Guidelines*: tipe artikel, batas kata, struktur section, gaya sitasi
- [ ] Konfirmasi template LaTeX Springer Nature (`sn-jnl.cls`)

---

## ⭐ Kunci sukses: GESER framing dari "DB" ke "lingkungan"

ESD dibaca oleh ilmuwan lingkungan/keputusan, **bukan** orang database.
Risiko #1 = **desk-reject karena dianggap paper computing**. Maka:

- [ ] Jadikan **kontribusi lingkungan + decision support** sebagai bintang utama
- [ ] Posisikan perbandingan database sebagai **metode**, bukan kontribusi utama
- [ ] Judul & abstrak menonjolkan *carbon*, *green IoT/smart building*, *decision*, *sustainability* — bukan "benchmark database"
- [ ] Buka Introduction dari masalah **karbon infrastruktur IoT 24/7**, bukan dari TimescaleDB/WiredTiger

---

## 🗺️ Roadmap (bertahap)

### Fase 0 — Konsolidasi & perencanaan
- [x] Gabungkan `_3` + `_4` menjadi satu naskah three-way (hindari *salami slicing*) — selesai di [`paper/main.tex`](paper/main.tex)
- [x] Tetapkan **1 RQ payung** + 3 sub-RQ (energi, emisi/CO₂eq, keputusan arsitektur)
- [x] Tetapkan rentang resolusi yang konsisten — **360p–6K** (three-way s.d. 5K; PG-BYTEA & PG+MinIO s.d. 6K; MongoDB di-skip di 6K)
- [x] Buat outline section final (lihat [Fase 3](#fase-3--penulisan))

### Fase 1 — Eksperimen & data
> Beban benchmarking di sini lebih ringan daripada track IT/SE; fokus ke kualitas pengukuran carbon.
- [x] **Ukur carbon per-resolusi secara LANGSUNG** dengan CodeCarbon — **sudah diimplementasikan** di [`code/`](code): satu tracker CodeCarbon per *engine × dimensi × resolusi* → `data/emissions.csv`, **bukan lagi** model estimasi konstan-daya. ⚠️ Sisa: pastikan **RAPL terbaca** (`setup_rapl.sh`) supaya energi benar-benar terukur hardware, bukan fallback estimasi TDP CodeCarbon.
- [x] Lengkapi **three-way**: MongoDB, PG-BYTEA, dan PG+MinIO diuji pada resolusi sama (360p–5K three-way; 6K untuk PG/PM) + retrieval **terpadu** (bulk + latest-frame) di ketiga engine
  - ⚠️ **Batas MongoDB di 6K**: payload 6K (inline BSON) melampaui batas **16 MiB** per-dokumen BSON → MongoDB **gagal & otomatis di-skip** di titik ini (harness: *retry-lalu-skip*, dicatat di [`code/`](code) → `data/skipped.csv`). PG-BYTEA & PG+MinIO tetap jalan di 6K. Perlakukan ini sebagai **temuan arsitektural**, bukan sekadar limitasi (lihat [Fase 2](#fase-2--analisis--kontribusi-lingkungan-pembeda-q2) & [Risiko](#-risiko--catatan)).
- [ ] Ukur **baseline idle power** tiap engine (untuk energy proportionality)
- [ ] (Opsional, nilai tambah) ulang dengan **dataset citra nyata**, bukan hanya JPEG sintetis
- [ ] Catat konfigurasi lengkap (shared_buffers, WAL, WiredTiger cache, dll.) untuk reprodusibilitas
- [~] **Variabilitas dilaporkan** (2026-06-10): CV per-operasi **≈1,6%** (median) untuk insert+bulk-retrieval, <8% terburuk; klaim "emisi = mean±SD 5-run" **dikoreksi** (carbon = 1 pengukuran terintegrasi per sel, dinormalisasi per-run; near-tie 4K Mongo–Postgre 1,8% dinyatakan "within noise"). Sisa: ulang **run energi independen** untuk CI carbon per-sel (carbon kini n=1).

### Fase 2 — Analisis & kontribusi lingkungan (pembeda Q2)
- [x] **Sensitivitas grid multi-region**: tabel emisi kumulatif untuk 7 grid (Swedia 41 → India 713 gCO₂/kWh); ranking PM<PG<MG invarian (energi-determined)
- [x] Nyatakan hasil dalam unit **SCI (Software Carbon Intensity, ISO/IEC 21031:2024)** — mg CO₂eq per 1000 frame (Tabel SCI)
- [x] **LCA ringan / embodied carbon**: amplifikasi 3× MongoDB @5K → ~3.2 kg embodied ekstra vs PM (faktor 0.16 kgCO₂/GB, ref Tannu&Nair/Gupta)
- [x] Sertakan faktor **PUE** data center (proyeksi fleet ×1.5)
- [x] **Proyeksi skala fleet**: 1000 kamera × 1 frame/menit × 1 thn @4K → PM hemat ~440 kg/thn vs PG (~2600 km mobil / ~21 pohon-tahun)
- [x] Bangun **decision framework / decision tree** carbon-aware (ini kait utama ke "...and Decisions")
  - Cabang **ukuran payload**: bila payload/sample mendekati/melebihi **16 MiB**, MongoDB inline-BSON **tidak layak** (lihat skip 6K di Fase 1) → arahkan ke arsitektur eksternalisasi objek (PG+MinIO). Constraint keras ini = titik keputusan konkret, bukan sekadar trade-off karbon.
- [x] Petakan kontribusi ke **SDG** (7, 9, 11, 12, 13)

### Fase 3 — Penulisan
> Naskah lengkap di [`paper/main.tex`](paper/main.tex) — kompilasi bersih (`sn-jnl`, **26 hlm, 6 gambar, 11 tabel, 3 listing (Appendix A), 42 sitasi**, 0 undefined/overfull).
> **Revisi editorial terbaru (2026-06-09):**
> - Bahasa disesuaikan untuk **audiens akademik umum/lingkungan** (bukan ilmuwan komputer); **setiap singkatan** diberi kepanjangan + penjelasan singkat + sumber pada penyebutan pertama (BSON, TOAST, BYTEA, RAPL, WAL, PUE, SCI, SDG, JPEG, NVMe, dll.).
> - Gambar **dwi-skala** (linear kiri + logaritmik kanan) untuk metrik rentang-lebar; **Fig. amplifikasi storage linear-only** (rasio menyentuh 0 → log tak terdefinisi, dijelaskan di caption).
> - **Istilah dibuat lebih umum**: *full-materialisation retrieval* → **bulk retrieval**; *point read* → **latest-frame read** (istilah teknis tetap disebut sekali dalam kurung).
> - **Tabel ringkasan pemenang per-operasi** (`tab:winners`, jadi §5.1) + **breakdown carbon per-operasi baca** (`tab:dimcarbon`): temuan kunci → **pemenang carbon = pemenang performa** di setiap operasi (carbon ∝ waktu).
> - **Sumber citra nyata + atribusi**: source image = foto **Durdle Door (Dorset, UK)** oleh JJ Perks via **Pexels** (lisensi bebas), disitasi di Methodology; payload = *collage deterministik dari foto nyata* (istilah "synthetic" dihapus).
> - **Keputusan: cukup citra nyata, bukan video** — tiap record adalah citra independen; biaya storage/energi bergantung pada ukuran+entropi payload, bukan relasi antar-frame → real video tak diperlukan untuk perbandingan storage. Klip video NASA dihapus dari `assets/` (sisakan hanya foto sumber).
> - **Abstrak dipangkas ke ≤250 kata (≈243)** sesuai pedoman ESD (150–250 kata).
> - **Listing schema+query ketiga arsitektur dipindah ke Appendix A**.
> - **Referensi diverifikasi** (cek DOI/URL satu per satu): perbaiki DOI Tannu&Nair, URL Shehabi→OSTI, DOI konsep CodeCarbon; **42 ref, 0 unused, 0 undefined**. Ekuivalensi km-mobil/pohon disitasi (DESNZ, Nowak&Crane).
>
> **Revisi 2026-06-10 — koreksi data besar + double-blind + 7 isu reviewer:**
> - ⚠️ **Koreksi normalisasi carbon 5×.** Tiap tracker CodeCarbon membungkus **seluruh 5 run** (`run_insert`/`run_retrieval` = 5×2.000 = 10.000 operasi), tetapi SCI/per-frame/fleet sebelumnya dibagi **2.000** → angka absolut **5× terlalu tinggi**. **Diperbaiki (Opsi A):** semua carbon dinormalisasi ke **satu run 2.000-frame** (÷ jumlah run) di `code/report.py` + seluruh tabel & teks. **Ranking, crossover, & semua persentase TIDAK berubah** — hanya absolut mg/g/kg (mis. fleet saving 440→**88 kg/thn**, per-frame PM 1.16→**0.232 mg**, kumulatif PM 15.6→**3.13 g**). Sekalian perbaiki **typo unit g→kg** di kalimat grid-saving (0.33 kg→**0.066 g**, 5.8 kg→**1.16 g**).
> - **Anonimisasi double-blind** (ESD = *double-anonymous*): author/afiliasi/email/acknowledgement/funding di-*comment* + placeholder `[Hidden for Double-blind Review]`; "Banten province"→"Indonesia"; self-reference "our earlier work"→netral `[hidden for double-blind review]`; **metadata 6 figur PDF di-strip** (PyMuPDF: hapus creator/producer/timestamp **WIB** + XMP). Naskah ter-render **bersih dari identitas** (diverifikasi skrip).
> - **7 isu reviewer ditangani:** (1) *scope/venue* — kontribusi+abstrak dibingkai sebagai **environmental-systems decision**; (3a) **normalisasi 5×** di atas; (3b) klaim "emisi=mean±SD 5-run" dikoreksi (carbon = 1 pengukuran terintegrasi; CV performa ≈1,6%), near-tie 4K Mongo–Postgre dilunakkan (1,8%, dalam noise); (4) embodied carbon dibingkai eksplisit **first-order/single-factor + boundary LCA**; (5) grid sweep = **rescaling linear**, SCI+embodied sebagai nilai carbon spesifik; (6) **pertahanan GridFS-inkompatibel-TS** ditambah di skema MongoDB (bukan *setup* lemah); (2) **baseline terkontrol** single-host/single-client dijustifikasi; (7) caveat **entropi-bukan-subjek** dipertajam.
> - `code/report.py` kini menghasilkan angka **per-run** (konsisten dgn paper); 6 figur diregenerasi + metadata di-strip ulang. Kompilasi bersih **26 hlm**, 0 undefined.
> - **Persiapan upload (akhir 2026-06-10):** author/ack/funding/Declarations **dihapus penuh** dari source `main.tex` (bukan sekadar *comment*) supaya source LaTeX aman di-upload; **blok Declarations diekstrak** → `declarations/` (teks siap-tempel per-field form ESD); **artifact siap-upload** dirakit di `zenodo/` (code+data+figures+paper anonim+README), dgn **geolokasi `data/emissions.csv` di-scrub** (region/lon/lat) pada salinan zenodo. `CONTEXT.md` & `declarations/` **dikecualikan** dari upload.
- [x] **Abstract** (terstruktur, tonjolkan carbon + keputusan + temuan 6K)
- [x] **Introduction** (motivasi karbon IoT, gap, 4 bullet kontribusi eksplisit)
- [x] **Related Work** dgn sub-bagian + **tabel pembanding** (payload size, metrik, energi ya/tidak) → gap visual
- [x] Kurangi sitasi blog vendor → tambah 4 ref peer-reviewed lingkungan (Masanet *Science*, Gupta *HPCA*, Tannu&Nair SSD-embodied, Shehabi/LBNL); doc engine tetap untuk detail internal
- [x] **Methodology** (hardware/repro table, CodeCarbon/RAPL **pengukuran langsung**, grid intensity, schema three-way, failover retry-skip)
- [x] **Results** (energi, emisi per-resolusi **terukur**, grid sensitivity, storage→embodied, retrieval terpadu, temuan 6K)
- [x] **Decision framework** (section tersendiri + tabel pemilihan)
- [x] **Discussion** (implikasi green building/IoT, mekanisme crossover, trade-off, threats to validity)
- [x] **Conclusion** + future work
- [x] Tambah **Data/Code Availability Statement**

### Fase 4 — Reprodusibilitas
- [x] **Rapikan kode benchmark + `docker-compose` + generator data** — harness OO (Strategy + Template Method) di [`code/`](code): satu entry point `run.py` (auto-venv, orkestrasi Docker, timing/ETA, **failover retry-lalu-skip**), `docker-compose.yml` (timescaledb + minio + mongodb), generator payload `payloads.py` (collage deterministik dari foto sumber), unit test (`tests/`, tanpa perlu DB).
- [x] **Sertakan raw results + analisis** — `data/`: CSV per-run + summary tiap dimensi, `emissions.csv` (CodeCarbon), `threeway_summary.csv` (agregat), `skipped.csv`; figur & agregasi dibangun via `code/report.py` (menggantikan notebook).
- [x] **Panduan reproduksi/build** — [`README.md`](README.md) baru: langkah-demi-langkah reproduce data & figur, build paper, dan cover letter, + penjelasan **data** dan **kode**; disiapkan untuk **upload Zenodo** (CONTEXT.md ini dikecualikan — dipakai personal). README roadmap lama di-*rename* → CONTEXT.md.
- [ ] Publikasikan artifact ke **Zenodo** → dapatkan **DOI**, tautkan di paper (Data/Code Availability masih `DOI to be added`).

### Fase 5 — Submission
- [x] Reformat ke **template Springer Nature** (`sn-jnl.cls`) — naskah sudah memakai `sn-jnl` (sn-basic), kompilasi bersih
- [x] **Tulis cover letter** — [`cover_letter/cover_letter.tex`](cover_letter/cover_letter.tex): **1 halaman**, bahasa non-teknis (audiens lingkungan), menekankan kontribusi lingkungan + decision support, dan **mengungkap dua companion conference paper** (diterima di **ATIGB**, UTE–UDN Vietnam, menunggu presentasi) untuk transparansi. ⚠️ Sisa: isi **nama editor** + **konfirmasi judul/tahun/tanggal pasti ATIGB** (`% TODO`); cover letter kini ~2 hlm karena tambahan disclosure.
- [ ] Cek **similarity** (hindari overlap teks dengan draf konferensi / Paper A)
- [x] (draft) Siapkan **daftar reviewer** — lihat bagian **Saran reviewer** di bawah (verifikasi afiliasi/email + COI sebelum submit)
- [ ] Submit via Editorial Manager
- [ ] Setelah terbit: **self-archive** *accepted manuscript* ke Zenodo/repositori (embargo Springer ~6 bln) agar bisa dibaca gratis

### Fase 6 — Pasca-submission
- [ ] Tangani *major/minor revision* (siapkan *response-to-reviewers* yang sistematis)
- [ ] Jika ditolak → *cascade* ke target lain (Sustainable Computing Q1 / EMA Q2 / STI $300)

---

## 📂 Sumber materi

| Dari | Ambil |
|---|---|
| [`alfa_yohannis_3.tex`](../postgre-vs-mongodb-carbon-footprint/paper/alfa_yohannis_3.tex) | Carbon PG vs MongoDB, breakdown CPU/RAM, tabel emisi per-resolusi |
| [`alfa_yohannis_4.tex`](../postgre-vs-postgre-minio-carbon-footprint/paper/alfa_yohannis_4.tex) | Carbon PG vs PG+MinIO, whole-phase totals, crossover analysis |
| Draf performa `_1`/`_2` | Ringkasan *supporting performance* (penjelas mekanistik kenapa carbon berbeda) |

---

## 💰 Strategi biaya & open access

- **Publikasi = gratis** lewat jalur subscription ESD (hybrid). Tidak perlu langganan institusi.
- Agar tetap bisa dibaca gratis → **self-archiving** AM (green OA, embargo ~6 bln).
- **Jangan** pilih gold OA berbayar; **jangan** andalkan waiver APC (Indonesia kemungkinan tak memenuhi syarat).

---

## ⚠️ Risiko & catatan
- **Batas dokumen MongoDB (16 MiB BSON)**: MongoDB inline-BSON tidak dapat menyimpan payload 6K → harness otomatis **retry-lalu-skip** dan mencatatnya di `data/skipped.csv`; three-way menjadi *two-way* **hanya di titik 6K**. Laporkan eksplisit (jangan disembunyikan) sebagai constraint arsitektural + jadikan input decision framework (Fase 2).
- **Akurasi energi bergantung pada RAPL**: carbon per-resolusi kini diukur **langsung** (CodeCarbon per resolusi, bukan estimasi konstan-daya), namun bila RAPL tak terbaca CodeCarbon jatuh ke estimasi TDP → jalankan `setup_rapl.sh` dan verifikasi sebelum run final.
- Tanpa kontribusi lingkungan yang kuat (Fase 2), editor lingkungan akan menilai ini "paper computing".
- Jaga konsistensi antar paper (companion): sitasi silang dengan Paper A, ungkap di cover letter.
- **Dua conference paper companion** (`alfa_yohannis_3/4.tex`, **diterima di ATIGB** [atigb.ute.udn.vn], menunggu presentasi) **wajib diungkap ke editor**: cover letter + deklarasi **Dual publication = Yes** (`declarations/dual_publication.txt`) + upload sebagai **Related Files** di Editorial Manager. **JANGAN** dimasukkan ke `zenodo/` atau `main.tex` — keduanya menyebut nama penulis (membocorkan double-blind). PDF perlu di-*compile* dari `_3.tex`/`_4.tex` untuk di-upload.

---

## ✅ Pre-submission consistency & publication-safety checklist (verified 2026-06-10)

> Re-run before each submission. `data/*.csv` is the **authoritative** source for every number;
> figures are generated by `code/report.py` from that data, so they never need manual editing.

**Data integrity (paper ⇄ data)**
- [x] **2026-06-10: semua carbon dinormalisasi per-run (÷ jumlah run).** Angka absolut di bawah = **per satu run 2,000-frame**; persentase & ranking invarian terhadap normalisasi. Tiap angka di abstrak/prosa/tabel dicocokkan ulang dgn `data/threeway_summary.csv` + `emissions.csv` (per-res carbon = Σ(insert+retrieve+point\_read)/run\_count, kg×1e6) — diverifikasi skrip.
- [x] **MongoDB 5K carbon (per-run) = 2,712.9 mg** (raw 5-run 13,564.4 ÷5). Klaim "MongoDB tertinggi kumulatif" tetap berlaku (rasio invarian).
- [x] Cumulative 360p–5K (per-run): Postgre **4.15 g** · Mongo **4.22 g (highest)** · PostMin **3.13 g** (−24.7% vs Postgre, −25.9% vs Mongo — persentase tak berubah).
- [x] SCI = **per-run insert carbon ÷ 2** (= raw insert ÷ 10); **all 8 resolutions** present.
- [x] Per-frame 4K: PostMin **0.232** / Postgre **0.399** / Mongo **0.506** mg, saving **0.167**; fleet **122/210/266 kg·yr⁻¹**, saving **88** (≈520 km mobil / ~4 pohon); grid table ÷5; **embodied (4.8/1.6 kg) UNCHANGED** (berbasis storage, bukan run-count).
- [x] **Figures regenerated** (`report.py`, per-run; plot 2,712.9 at 5K) **+ PDF metadata stripped** (double-blind).

**Terminology / labels**
- [x] Architectures **Postgre / Mongo / PostMin** consistent in all table headers (no stray `MongoDB`/`PG`/`MG`/`PM` in headers).
- [x] Read ops **bulk retrieval** / **latest-frame read**; "full materialisation"/"point read" appear only once, in the definition.
- [x] No leftover `synthetic` / NASA / real-video text; payloads = "deterministic collages from a real photograph".
- [x] "4.8–23×" used consistently (Results bullet + decision table).

**References**
- [x] 42 cited = 42 defined; **0 unused, 0 undefined**.
- [x] DOIs/URLs verified: Tannu&Nair `10.1145/3630614.3630616`; Shehabi → OSTI `1372902`; CodeCarbon concept DOI `10.5281/zenodo.4658424`.
- [x] Source image attributed: JJ Perks / Pexels / Durdle Door (2021, Pexels License).

**Build / structure**
- [x] Compiles clean: **26 pp, 0 undefined, 0 overfull** (`latexmk -pdf` + bibtex).
- [x] Abstract **≤ 250 words** (≈243).
- [x] 6 figures + all tables referenced in text; figure PDFs present in `figures/`.
- [x] Declarations + AI-assistance disclosure present.

**Tone / language**
- [x] No exaggerated or overclaimed wording: removed "dramatically", "by far" (×2), "extraordinarily", "extremely", "outright", "robust pivot"→"pivot"; vivid verbs softened ("crushes/defeats/fails/regime change/hard wall"). Every claim is carried by the measured numbers.
- [x] Plain-language framing for a non-CS / environmental audience (abbreviations expanded in the paper; cover letter kept jargon-free).
- [x] Cover letter is **one page**, in `cover_letter/cover_letter.tex` (still has `% TODO` editor name + conference venue).

**Open items (author action before submit)**
- [ ] **Verify Docker Compose version** in environment table (currently "Compose v5.1.1" — unusual; not recorded by CodeCarbon, so confirm against the actual machine).
- [ ] Fill **Zenodo DOI** in Data/Code availability (currently "DOI to be added").
- [ ] Add **conference-paper venue/status** in the cover letter (companion-work disclosure, `% TODO` in `cover_letter/cover_letter.tex`).
- [ ] Similarity check vs the two conference drafts.
- [x] **Double-blind done** (2026-06-10): author/ack/funding/Declarations **dihapus** dari source `main.tex` (placeholder anonim; original di git) → source LaTeX aman di-upload; metadata 6 figur di-strip. ⚠️ **Restore author block dari git** untuk *camera-ready* setelah accept.
- [x] **Declarations diekstrak** → `declarations/` (teks siap-tempel per field form ESD; **jangan** di-upload bersama naskah/Zenodo — memuat identitas).
- [x] **Artifact `zenodo/` dirakit** → dibundel jadi **`README.md` + `artifact.zip`** (hanya 2 file untuk upload; geolokasi `emissions.csv` di-scrub). **Review link Zenodo ditambahkan** (draft preview: record 20625061) ke `data_availability.txt` + cover letter. ⚠️ **Verifikasi metadata record Zenodo** (Creators/Title/Description) juga anonim — halaman preview menampilkan nama walau file di dalamnya bersih. Sisa: pilih **LICENSE** (di form Zenodo), (opsional) source image di `code/assets/`.
- [x] Suggested-reviewer list **ready**: 5 candidates with verified university profile pages + institutional emails (see **Saran reviewer** below) — re-confirm just before submitting.

---

## 👥 Saran reviewer (5 nama — semua punya halaman profil universitas + email institusional)

> Dipilih **early/mid-career** (lebih mungkin menerima undangan review daripada nama senior yang sibuk), menutup facet utama paper: carbon **penyimpanan**, **embodied carbon**, **pengukuran energi software**, **carbon-aware decision**, **green IoT**. Halaman profil & email **diverifikasi dari laman resmi universitas (2026-06-09)**. Semua **bebas COI** thd Universitas Pradita / Universitas Multimedia Nusantara. Tetap **cek ulang** sesaat sebelum submit (orang bisa berpindah).

| # | Nama | Posisi / Afiliasi | Email institusional | Halaman profil universitas | Relevansi |
|---|---|---|---|---|---|
| 1 | **Varsha Rao** | PhD student, Dept. of Computer Science, University of Chicago, USA | `varsharao@uchicago.edu` | https://computerscience.uchicago.edu/people/varsha-rao/ | Carbon footprint **penyimpanan** (SSD vs HDD) — "Operational Carbon Footprint of Storage" (HotCarbon'24) |
| 2 | **Thibault Pirson** | Research Assistant / Invited Lecturer, ICTEAM, UCLouvain, Belgia | `thibault.pirson@uclouvain.be` | https://www.uclouvain.be/en/people/thibault.pirson | **Embodied carbon** perangkat IoT (LCA bottom-up, *J. Cleaner Production* 2021) → cocok utk analisis embodied + skala fleet |
| 3 | **Benjamin Weigell** | Research Assistant (M.Sc.), Software Methodologies for Distributed Systems, University of Augsburg, Jerman | `benjamin.weigell@uni-augsburg.de` | https://www.uni-augsburg.de/en/fakultaet/fai/informatik/prof/swtpvs/team/benjamin-weigell/ | **Pengukuran energi software** akurat (framework METRION) → menilai metode CodeCarbon/RAPL |
| 4 | **Lauritz Thamsen** | Lecturer, School of Computing Science, University of Glasgow, UK | `Lauritz.Thamsen@glasgow.ac.uk` | https://www.gla.ac.uk/schools/computing/staff/lauritzthamsen/ | **Carbon-aware computing** (memimpin lab GC3) → decision framework + proyeksi fleet |
| 5 | **Moysis Symeonidis** | Postdoctoral Research Associate, Lab. of Internet Computing (LInC), University of Cyprus, Siprus | `symeonidis.moysis@ucy.ac.cy` | https://linc.ucy.ac.cy/index.php?id=147 | Energi/carbon **layanan IoT** + benchmarking edge & model estimasi daya → framing green IoT |

⚠️ **Sebelum submit:** (1) konfirmasi email & halaman profil masih aktif; (2) email Symeonidis tampil ter-*obfuscate* `symeonidis.moysis_AT_ucy.ac.cy` di laman lab → ganti `_AT_` → `@`; (3) email Weigell di laman resmi = `@uni-augsburg.de` (alias `@uni-a.de` juga dipakai institusi); (4) di Editorial Manager beri **2–3 baris justifikasi** tiap reviewer; slate sudah tersebar lintas negara (USA, Belgia, Jerman, UK, Siprus).

*Alternatif senior* (hanya bila editor minta nama mapan — cenderung sibuk/menolak undangan): Eric Masanet (UC Santa Barbara), Udit Gupta (Cornell Tech), Swamit Tannu (UW–Madison), Arman Shehabi (LBNL), Loïc Lannelongue (Cambridge) — semuanya disitasi di paper.

---

*Status:* `draft lengkap + cover letter 1-hlm + checklist QA. **2026-06-10: koreksi normalisasi carbon 5× (Opsi A) + anonimisasi double-blind penuh (naskah author/ack/Declarations dihapus; metadata 6 figur + geolokasi emissions.csv di-scrub) + 7 isu reviewer ditangani + Declarations → declarations/ + artifact siap-upload di zenodo/ → 26 hlm, kompilasi bersih.** Fase 1–3 selesai; Fase 4 sebagian (sisa: LICENSE + publish Zenodo + DOI); Fase 5 (sisa: isi editor/venue TODO, similarity, isi field declarations di Editorial Manager, submit). Verifikasi versi Docker Compose sebelum submit.` · *Terakhir diperbarui:* 2026-06-10
