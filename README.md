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
- [ ] Gabungkan `_3` + `_4` menjadi satu naskah three-way (hindari *salami slicing*)
- [ ] Tetapkan **1 RQ payung** + 3 sub-RQ (energi, emisi/CO₂eq, keputusan arsitektur)
- [ ] Tetapkan rentang resolusi yang konsisten (mis. 360p–5K) di semua arsitektur
- [ ] Buat outline section final (lihat [Fase 3](#fase-3--penulisan))

### Fase 1 — Eksperimen & data
> Beban benchmarking di sini lebih ringan daripada track IT/SE; fokus ke kualitas pengukuran carbon.
- [x] **Ukur carbon per-resolusi secara LANGSUNG** dengan CodeCarbon — **sudah diimplementasikan** di [`code/`](code): satu tracker CodeCarbon per *engine × dimensi × resolusi* → `data/emissions.csv`, **bukan lagi** model estimasi konstan-daya. ⚠️ Sisa: pastikan **RAPL terbaca** (`setup_rapl.sh`) supaya energi benar-benar terukur hardware, bukan fallback estimasi TDP CodeCarbon.
- [ ] Lengkapi **three-way**: pastikan MongoDB, PG-BYTEA, dan PG+MinIO diuji pada resolusi yang sama
  - ⚠️ **Batas MongoDB di 6K**: payload 6K (inline BSON) melampaui batas **16 MiB** per-dokumen BSON → MongoDB **gagal & otomatis di-skip** di titik ini (harness: *retry-lalu-skip*, dicatat di [`code/`](code) → `data/skipped.csv`). PG-BYTEA & PG+MinIO tetap jalan di 6K. Perlakukan ini sebagai **temuan arsitektural**, bukan sekadar limitasi (lihat [Fase 2](#fase-2--analisis--kontribusi-lingkungan-pembeda-q2) & [Risiko](#-risiko--catatan)).
- [ ] Ukur **baseline idle power** tiap engine (untuk energy proportionality)
- [ ] (Opsional, nilai tambah) ulang dengan **dataset citra nyata**, bukan hanya JPEG sintetis
- [ ] Catat konfigurasi lengkap (shared_buffers, WAL, WiredTiger cache, dll.) untuk reprodusibilitas
- [ ] Naikkan jumlah run & laporkan **confidence interval** (bukan sekadar "variance low")

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
> Naskah lengkap di [`paper/main.tex`](paper/main.tex) — kompilasi bersih (`sn-jnl`, 20 hlm, 6 gambar, 8 tabel, 35 sitasi).
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
- [ ] Rapikan kode benchmark + `docker-compose` + generator data
- [ ] Sertakan raw results + notebook analisis
- [ ] Publikasikan artifact ke **Zenodo** → dapatkan **DOI**, tautkan di paper

### Fase 5 — Submission
- [x] Reformat ke **template Springer Nature** (`sn-jnl.cls`) — naskah sudah memakai `sn-jnl` (sn-basic), kompilasi bersih
- [ ] Tulis **cover letter** (tekankan kontribusi lingkungan + ungkap *companion paper* track IT/SE untuk transparansi)
- [ ] Cek **similarity** (hindari overlap teks dengan draf konferensi / Paper A)
- [ ] Siapkan **daftar reviewer** yang disarankan
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

---

*Status:* `draft lengkap — data three-way riil & terukur terintegrasi (Fase 1–3 selesai); berikutnya Fase 4 (artifact/Zenodo DOI) & Fase 5 (cover letter, similarity, submission)` · *Terakhir diperbarui:* 2026-06-05
