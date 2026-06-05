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
- [ ] **Ukur carbon per-resolusi secara LANGSUNG** dengan CodeCarbon (fase ter-tracking terpisah per resolusi) — **ganti model estimasi konstan-daya** yang sekarang dipakai
- [ ] Lengkapi **three-way**: pastikan MongoDB, PG-BYTEA, dan PG+MinIO diuji pada resolusi yang sama
- [ ] Ukur **baseline idle power** tiap engine (untuk energy proportionality)
- [ ] (Opsional, nilai tambah) ulang dengan **dataset citra nyata**, bukan hanya JPEG sintetis
- [ ] Catat konfigurasi lengkap (shared_buffers, WAL, WiredTiger cache, dll.) untuk reprodusibilitas
- [ ] Naikkan jumlah run & laporkan **confidence interval** (bukan sekadar "variance low")

### Fase 2 — Analisis & kontribusi lingkungan (pembeda Q2)
- [ ] **Sensitivitas grid multi-region**: hitung ulang emisi untuk beberapa intensitas grid (mis. Indonesia, India batubara-berat, EU, Nordik terbarukan)
- [ ] Nyatakan hasil dalam unit **SCI (Software Carbon Intensity, Green Software Foundation)** — mis. gCO₂eq per 1000 frame
- [ ] **LCA ringan / embodied carbon**: amplifikasi storage 3× MongoDB → lebih banyak SSD → emisi embodied + wear/endurance
- [ ] Sertakan faktor **PUE** data center (operasional vs total)
- [ ] **Proyeksi skala fleet**: mis. kota dengan N kamera × 1 tahun → kg/ton CO₂eq + ekuivalen relatable (km mobil / pohon)
- [ ] Bangun **decision framework / decision tree** carbon-aware (ini kait utama ke "...and Decisions")
- [ ] Petakan kontribusi ke **SDG** (7, 9, 11, 12, 13)

### Fase 3 — Penulisan
- [ ] **Abstract** (terstruktur, tonjolkan carbon + keputusan)
- [ ] **Introduction** (motivasi karbon IoT, gap, kontribusi eksplisit — buat daftar bullet kontribusi)
- [ ] **Related Work** dgn sub-bagian + **tabel pembanding** (payload size, metrik, energi ya/tidak) → tunjukkan gap visual
- [ ] Kurangi sitasi blog vendor → ganti sumber peer-reviewed (LCA, green computing, energy-aware systems)
- [ ] **Methodology** (hardware, CodeCarbon/RAPL, grid intensity, three-way schema)
- [ ] **Results** (energi, emisi per-resolusi *terukur*, grid sensitivity, storage→embodied)
- [ ] **Decision framework** (section tersendiri)
- [ ] **Discussion** (implikasi green building/IoT, trade-off, threats to validity)
- [ ] **Conclusion** + future work
- [ ] Tambah **Data/Code Availability Statement**

### Fase 4 — Reprodusibilitas
- [ ] Rapikan kode benchmark + `docker-compose` + generator data
- [ ] Sertakan raw results + notebook analisis
- [ ] Publikasikan artifact ke **Zenodo** → dapatkan **DOI**, tautkan di paper

### Fase 5 — Submission
- [ ] Reformat ke **template Springer Nature** (`sn-jnl.cls`)
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
- Titik lemah utama saat ini = **carbon per-resolusi masih diestimasi** → wajib diukur langsung (Fase 1).
- Tanpa kontribusi lingkungan yang kuat (Fase 2), editor lingkungan akan menilai ini "paper computing".
- Jaga konsistensi antar paper (companion): sitasi silang dengan Paper A, ungkap di cover letter.

---

*Status:* `belum mulai` · *Terakhir diperbarui:* 2026-06-04
