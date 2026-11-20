# SEO Content Intelligence

Workbench editorial untuk mengubah satu kata kunci menjadi satu paket artikel SEO
yang dapat ditelusuri sumbernya. Pipeline membantu riset, brief, penulisan, optimasi,
QA dan ekspor. **Manusia tetap menyetujui kata kunci, brief dan artikel akhir.**
Hasil dapat diunduh atau dikirim sebagai pull request ke repositori blog GitHub.

> MVP ini belum memiliki autentikasi/otorisasi dan ditujukan untuk satu operator.
> Jangan mengekspos API/workbench langsung ke internet. Gunakan jaringan privat atau
> lapisan akses terautentikasi. Build produksi bukan jaminan aman untuk layanan publik.

## Alur kerja

1. **Proyek:** isi website (termasuk base path), niche, audiens, bahasa/negara, gaya
   bahasa, tujuan bisnis dan aturan editorial. Impor inventaris dari daftar URL
   atau sitemap untuk mendeteksi tumpang tindih dengan konten yang sudah ada.
2. **Riset keyword:** mode selected memakai kata kunci pilihan; discovery membuat
   shortlist dari seed. Lihat metrik beserta provider/waktu pengambilan, SERP,
   intent, alasan/confidence skor peluang dan overlap inventaris. Data yang tidak
   tersedia ditandai unavailable, bukan diisi angka rekaan.
3. **Gerbang manusia 1 — keyword review:** pilih kandidat dan konfirmasi/ubah intent.
4. **Strategi dan brief:** angle, diferensiasi, outline H1/H2/H3 dengan tujuan tiap
   bagian, pertanyaan, batasan, rencana sumber dan internal link berbasis inventaris.
   Link yang belum terdaftar menjadi saran pencarian.
5. **Gerbang manusia 2 — brief review:** edit dan setujui brief sebelum penulisan.
6. **Riset bukti dan draft:** pustaka sumber menyimpan URL, publisher, waktu dan
   provenance. Evidence ledger menghubungkan klaim dengan sumber, catatan pendukung,
   confidence dan status verifikasi. Teks sumber adalah data tidak tepercaya,
   bukan instruksi untuk model.
7. **SEO dan QA:** metadata, slug, arahan gambar dan artikel diperiksa dalam enam
   dimensi: pemenuhan intent, akurasi/bukti, nilai orisinal, kualitas editorial,
   kelengkapan on-page, serta kepercayaan/akuntabilitas. Aturan deterministik
   memeriksa angka tanpa dukungan, heading, internal link/self-link, benturan slug,
   deskripsi meta dan keyword stuffing. Masalah dapat memicu revisi terbatas atau
   status blocked untuk koreksi manual.
8. **Gerbang manusia 3 — final review:** tinjau Markdown, versi/diff, SEO dan QA;
   setujui versi terbaru atau minta revisi dengan komentar. Edit manual membuat
   versi baru dan menjalankan QA tanpa menimpa versi itu secara diam-diam. Konten
   YMYL memerlukan pengakuan expert review dan komentar manusia.
9. **Ekspor:** setelah persetujuan akhir, worker menghasilkan Markdown, HTML dan
   JSON. JSON menyertakan metadata, versi, brief, sumber, evidence ledger dan QA.
10. **Opsional — GitHub:** kirim artikel sebagai PR ke repo blog; editor masih
    harus meninjau dan merge sendiri. Tidak ada penerbitan situs otomatis.

Audit log mencatat state, persetujuan, percobaan job, error, token dan biaya.
UI melakukan polling tiap dua detik saat ada job aktif. QA bukan pemeriksa fakta
semantik lengkap, dan skor peluang bukan jaminan ranking.

## Arsitektur

```mermaid
flowchart LR
    Editor[Editor manusia] --> Web[Next.js App Router / TypeScript]
    Web -->|rewrite same-origin /api| API[FastAPI]
    API --> DB[(PostgreSQL / SQLite)]
    DB --> Worker[Worker antrean terpisah]
    Worker --> Graph[LangGraph StateGraph]
    Graph <--> Checkpoint[(PostgresSaver / SqliteSaver)]
    Graph --> Providers[Mock / LiteLLM / DataForSEO]
    Graph --> DB
    Graph --> Gates[Approval keyword / brief / final]
    Gates --> Editor
    Graph --> Export[Ekspor MD / HTML / JSON]
    API -->|aksi eksplisit editor| GitHub[PR repositori blog GitHub]
```

- **FastAPI + SQLAlchemy 2** memvalidasi perintah dan menyimpan proyek, artefak,
  versi dan job. Pipeline berjalan di worker, bukan request HTTP. Impor sitemap
  dan pengiriman PR GitHub adalah konektor sinkron di API.
- **LangGraph** menyimpan checkpoint dengan run ID sebagai thread ID. Gerbang
  memakai `interrupt()` dan dilanjutkan melalui `Command(resume=...)`.
- **PostgreSQL** mendukung klaim job dengan `FOR UPDATE SKIP LOCKED`; **SQLite**
  memakai write lock. Heartbeat menjaga lease job aktif; lease tanpa pembaruan
  selama sepuluh menit dapat diambil kembali. Gunakan satu worker untuk SQLite.
- **LiteLLM** mengakses model nyata. **DataForSEO** menyediakan SERP, metrik/saran
  keyword dan penemuan sumber. Pemilihan mock untuk keduanya saling independen.
- **Next.js** meneruskan request browser `/api` ke backend melalui rewrite server.
  Kredensial provider dan GitHub tetap di server.

### Tata letak repositori

```text
backend/
  seoci/api/             # endpoint FastAPI dan schema input
  seoci/pipeline/        # graph, state machine, scoring dan QA
  seoci/providers/       # LiteLLM, DataForSEO, mock, riset, sitemap, cache/network
  seoci/config.py        # settings backend
  seoci/db.py            # koneksi SQLAlchemy
  seoci/models.py        # model data
  seoci/worker.py        # konsumen antrean database
  seoci/export.py        # rendering dan paket ekspor
  seoci/publish_github.py # branch, file Astro dan PR GitHub
  alembic/               # migrasi schema
  tests/                 # pengujian offline dan API + worker
  seed.py                # data demo melalui API yang sedang berjalan
  demo.py                # walkthrough curl sampai unduhan Markdown
  README.md              # kontrak API rinci
frontend/
  app/                   # halaman dashboard, proyek dan run
  components/            # form dan panel workbench
  lib/                   # client API, tipe dan helper/test frontend
scripts/dev.sh           # tiga proses development
docker-compose.yml       # PostgreSQL 16, API, worker, web
Makefile                 # dev, seed, check
.github/workflows/ci.yml  # pemeriksaan backend/frontend
```

## Development lokal — SQLite

Prasyarat: `uv`, Python 3.12 (dapat dipasang oleh uv), Node.js 20.9+ dan npm.
Paket Python mensyaratkan minimal 3.11; script, CI dan image memakai 3.12.
Semua perintah dimulai dari **root repositori**, kecuali disebutkan lain.

```sh
make dev
```

Alternatif setara: `./scripts/dev.sh`. Script memasang dependensi dengan uv/npm,
menjalankan migrasi Alembic, lalu menyalakan API pada 8000, worker, dan Next.js
development pada 3000. Hentikan dengan Ctrl+C. Jangan menyalakan dua stack pada
port yang sama. Script frontend mengikat semua antarmuka; gunakan jaringan
tepercaya atau firewall untuk membatasi akses.

Di terminal lain, setelah API dan worker siap:

```sh
make seed
```

`backend/seed.py` membuat proyek Kebun Balkon, inventaris, satu discovery run pada
keyword review dan satu contoh yang sudah diekspor. Seed menyetujui gerbang demo
secara otomatis; gunakan hanya untuk data uji, bukan konten nyata.
Buka **http://localhost:3000**; API ada di **http://127.0.0.1:8000**, dan dokumentasi
interaktif di **http://127.0.0.1:8000/docs**. Pipeline mock tidak memerlukan API key.
Impor sitemap dan publishing GitHub tetap operasi jaringan eksplisit meskipun
provider pipeline memakai mock.

## Docker Compose — PostgreSQL 16

Prasyarat: Docker dengan plugin Compose. Bebaskan port host 8000 dan 3000.

```sh
docker compose config -q
docker compose up --build
```

Di terminal lain setelah API sehat dan worker siap:

```sh
docker compose exec api python seed.py
# Opsional: walkthrough curl sampai ekspor melalui API host pada port 8000
(cd backend && uv sync --frozen --python 3.12 && uv run python demo.py)
```

Compose menjalankan migrasi sebelum API, menunggu PostgreSQL sehat sebelum API,
dan API sehat sebelum worker/web. API/web hanya dipublikasikan pada
`127.0.0.1:8000` dan `127.0.0.1:3000`; PostgreSQL tidak membuka port host.
Web dibangun dengan proxy internal `http://api:8000`. Database dan checkpoint
bertahan di named volume `pgdata`.

```sh
# Hentikan container tanpa menghapus volume
docker compose down
```

Jangan menambahkan opsi `-v` kecuali ingin menghapus volume database. Ganti
`POSTGRES_PASSWORD` bawaan sebelum penggunaan selain demo lokal. Compose merangkai
password ke URL koneksi; bila perlu URL-encoding, sesuaikan konfigurasi URL koneksi
secara konsisten. Lindungi file rahasia dan backup data sebelum perubahan.

## Build produksi tanpa Docker

Siapkan PostgreSQL untuk deployment dengan beberapa worker; SQLite tetap tersedia
untuk satu operator. Atur `DATABASE_URL` sesuai database deployment, dengan format
`postgresql+psycopg://user:pass@host:5432/database` (contoh format, bukan kredensial
siap pakai). API, worker dan Alembic harus menggunakan database yang **sama**.

1. Isi `backend/.env` atau environment proses sesuai tabel konfigurasi. Ekspor
   kunci LiteLLM ke environment proses bila menggunakan model nyata.
2. Pasang dependensi dan jalankan migrasi **sebelum** menyalakan kode baru:

   ```sh
   (cd backend && uv sync --frozen --python 3.12 && uv run alembic upgrade head)
   (cd frontend && npm ci && BACKEND_URL=http://127.0.0.1:8000 npm run build)
   ```

   Migrasi mencakup heartbeat job dan pengaturan publishing. Pembuatan tabel saat
   startup tidak menggantikan migrasi database lama.
3. Jalankan tiga proses pada terminal/service manager terpisah, dari root repo:

   ```sh
   # Proses API
   (cd backend && uv run uvicorn seoci.api.main:app --host 127.0.0.1 --port 8000)
   ```

   ```sh
   # Proses worker: wajib; API saja tidak menjalankan pipeline
   (cd backend && uv run python -m seoci.worker)
   ```

   ```sh
   # Proses web: next start melalui script npm, bukan next dev
   (cd frontend && npm run start -- --hostname 127.0.0.1 --port 3000)
   ```

4. Periksa API dan proxy frontend:

   ```sh
   curl -fsS http://127.0.0.1:8000/api/health
   curl -fsS http://127.0.0.1:3000/api/health
   ```

   Keduanya seharusnya mengembalikan `{"status":"ok","pipeline":"separate-worker"}`.
   Health endpoint tidak membuktikan worker hidup; periksa log dan progres job.

**`BACKEND_URL` harus benar saat `next build`**, karena rewrite disimpan di hasil
build. Mengubahnya hanya saat `next start` tidak cukup; bangun ulang frontend jika
alamat API berubah. Pada Compose, sesuaikan build arg `BACKEND_URL` layanan web
bila topologi backend berubah, bukan hanya environment runtime.

Repo tidak menyediakan unit service atau konfigurasi reverse proxy produksi.
Gunakan service manager untuk restart/log dan lapisan akses privat yang sesuai.
Untuk SQLite default, backup **keduanya**: `backend/data/seoci.db` dan
`backend/data/seoci.db.checkpoints`, termasuk jurnal yang diperlukan saat backup
aktif. Lokasi relatif mengikuti direktori kerja backend. Untuk PostgreSQL, backup
database aplikasi beserta tabel checkpoint. Jangan menyimpan token di Git/browser.

## Konfigurasi lingkungan

Sumber: [`backend/seoci/config.py`](backend/seoci/config.py),
[`docker-compose.yml`](docker-compose.yml),
[`frontend/next.config.ts`](frontend/next.config.ts), serta Dockerfile backend/web.

- Pydantic membaca settings backend dari environment proses atau `.env` relatif
  terhadap direktori kerja: dengan perintah di atas, gunakan `backend/.env`.
  Environment proses mengungguli `.env`. API dan worker perlu konfigurasi identik.
- Kunci provider LiteLLM harus tersedia di **environment proses**. Jangan
  mengandalkan file settings `backend/.env` saja untuk kunci di luar field Settings.
- Compose memakai `.env` root untuk substitusi `${...}`; hanya variabel yang
  dipetakan pada `environment` yang diteruskan ke container. `CACHE_TTL_SECONDS`,
  `NETWORK_TIMEOUT` dan `WORKER_POLL_SECONDS` belum dipetakan: tambahkan ke API
  **dan** worker bila ingin mengubahnya. `DATABASE_URL` Compose dirangkai langsung;
  environment host dengan nama yang sama tidak otomatis menggantikannya.

### Settings backend dan provider

| Variabel | Bawaan | Fungsi |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./data/seoci.db` | Database SQLAlchemy dan dasar lokasi checkpoint; Compose memakai PostgreSQL. |
| `LLM_MODEL` | kosong | Kosong memilih mock; isi identifier LiteLLM seperti `openai/gpt-4o-mini` untuk model nyata. |
| `OPENAI_API_KEY` | tidak disetel aplikasi | Kunci OpenAI, dibaca LiteLLM; Compose meneruskan nilai atau string kosong. |
| `ANTHROPIC_API_KEY` | tidak disetel aplikasi | Kunci Anthropic bila identifier LiteLLM memakai provider itu; Compose juga meneruskannya. |
| `SERP_PROVIDER` | `mock` | `mock` atau `dataforseo`; mengendalikan SERP, keyword dan penemuan sumber riset. |
| `DATAFORSEO_LOGIN` | kosong | Login akun DataForSEO. |
| `DATAFORSEO_PASSWORD` | kosong | Password akun DataForSEO. |
| `MAX_REVISION_CYCLES` | `2` | Batas siklus revisi otomatis QA dan permintaan revisi akhir yang berbagi penghitung. |
| `RUN_BUDGET_USD` | `2.0` | Menolak task model berikutnya ketika biaya tercatat mencapai batas; bukan reservasi biaya sebelum panggilan. |
| `CACHE_TTL_SECONDS` | `3600` | Masa berlaku cache provider dalam detik. |
| `NETWORK_TIMEOUT` | `20` | Timeout request jaringan/model dalam detik. |
| `WORKER_POLL_SECONDS` | `0.5` | Interval pencarian job saat antrean kosong. |
| `GITHUB_TOKEN` | kosong | Token backend untuk membuat branch, file dan PR pada repo blog. |
| `GITHUB_API_URL` | `https://api.github.com` | Base URL REST API GitHub untuk konektor publishing. |

Pemilihan provider **bukan satu sakelar global**:

| Kondisi | Hasil |
|---|---|
| `LLM_MODEL` kosong | `MockLLMClient`; tanpa panggilan model berbayar. |
| `LLM_MODEL` terisi | `LiteLLMClient`; butuh kredensial provider model. |
| `SERP_PROVIDER=mock` | Mock SERP/keyword dan sumber demo; metrik yang tidak ada tetap unavailable. |
| `SERP_PROVIDER=dataforseo` | SERP/keyword DataForSEO nyata; riset sumber mengikuti SERP. Butuh kedua kredensial DataForSEO. |

Mengisi API key saja tidak mengaktifkan provider nyata. Memilih provider nyata
tanpa kredensial menghasilkan error; tidak ada fallback diam-diam ke mock.
Mode campuran didukung, tetapi LLM nyata dengan SERP mock tetap menerima sumber
demo. Untuk provider LiteLLM lain, ikuti variabel kredensial provider tersebut dan
teruskan secara eksplisit ke proses/container. Tabel di atas mencakup integrasi
yang dipetakan repo, bukan seluruh katalog LiteLLM.

Mock membuat artikel Indonesia/Inggris, contoh hipotetis dan referensi awal
berlabel demo, bukan riset web terverifikasi. Revisi mock mempertahankan teks lama
dan menambah checklist bila ada instruksi; revisi semantik tetap manual. Riset
bawaan memakai snippet SERP, bukan pengambilan halaman penuh. Publikasi nyata tetap
memerlukan verifikasi sumber manusia, termasuk dengan provider live. Panggilan
terakhir bisa melampaui budget karena biaya diketahui sesudah respons. Data
proyek/brief/riset dikirim ke provider yang dipilih saat mode nyata digunakan.

### Web, database Compose dan utilitas

| Variabel | Bawaan/pemakaian dalam repo | Keterangan |
|---|---|---|
| `BACKEND_URL` | Next lokal: `http://127.0.0.1:8000`; Docker: `http://api:8000` | Tujuan rewrite `/api` saat build; jangan tambahkan `/api` pada nilainya. |
| `API_URL` | `http://127.0.0.1:8000` | Base URL `backend/seed.py`, tanpa `/api`; `backend/demo.py` menetapkan port 8000 langsung. |
| `POSTGRES_PASSWORD` | `seoci_local_only` pada Compose | Password database dan komponen URL API/worker; ganti untuk deployment. |
| `POSTGRES_DB` | `seoci` | Environment container PostgreSQL, ditetapkan literal di Compose; bukan substitusi `.env` host. |
| `POSTGRES_USER` | `seoci` | User container PostgreSQL, juga ditetapkan literal di Compose. |
| `NODE_ENV` | `production` pada image web runtime | Diatur Dockerfile web untuk proses produksi. |
| `NEXT_TELEMETRY_DISABLED` | `1` pada image web dan CI build | Menonaktifkan telemetri Next.js. |
| `PYTHONUNBUFFERED` | `1` pada image backend | Log Python tanpa buffering. |
| `PATH` | Image backend menambahkan `/app/.venv/bin` di depan nilai yang ada | Pengaturan internal Dockerfile agar executable venv ditemukan; tidak perlu diubah untuk quickstart. |

## Mengirim artikel ke repositori blog GitHub

1. Siapkan fine-grained token untuk repo blog tujuan dengan izin **Contents:
   read/write** dan **Pull requests: read/write**. Simpan sebagai `GITHUB_TOKEN`
   pada server, bukan profil proyek/frontend. Compose meneruskannya ke API/worker;
   jangan commit `.env`.
2. Isi pengaturan profil proyek (ini **field proyek**, bukan env var):

   ```json
   {
     "publishing": {
       "github_repo": "owner/name",
       "base_branch": "main",
       "content_dir": "src/content/blog",
       "file_extension": "md"
     }
   }
   ```

   Repository harus `owner/name`; branch tujuan harus sudah ada. Default direktori
   konten adalah `src/content/blog`, wajib path relatif tanpa segmen kosong, `.`
   atau `..`. Hanya `md` diterima, bukan MDX. Sesuaikan direktori dan periksa
   kompatibilitas schema konten blog tujuan.
3. Selesaikan persetujuan dan ekspor lalu klik **Kirim PR ke GitHub**. Endpoint
   `POST /api/runs/{id}/publish/github` menerima run `article_ready` atau `exported`;
   UI menampilkan tombol setelah ekspor tersedia.

Konektor membuat branch `seoci/<slug>-<8 karakter awal run ID>`, menulis
`<content_dir>/<slug>.md` dengan frontmatter `title`, `description`, `pubDate`, dan
`tags` bila ada, lalu membuka PR berisi keyword, run ID dan status QA. Ia **tidak
merge, tidak menulis langsung ke base branch, dan tidak menerbitkan situs otomatis**.
File yang sudah ada pada base branch ditolak agar tidak tertimpa. Sesudah berhasil,
permintaan berulang mengembalikan link PR tersimpan. Bila gagal setelah membuat
branch/file, periksa GitHub sebelum retry: branch yang sudah ada tidak ditimpa dan
bisa menghasilkan error validasi.

## Pemeriksaan dan referensi API

```sh
make check
# Test helper frontend tambahan; belum termasuk make check atau CI
(cd frontend && node --test lib/*.test.mjs)
```

`make check` menjalankan Ruff/pytest backend, lalu lint, typecheck dan build
frontend. CI di `.github/workflows/ci.yml` menjalankan pemeriksaan tersebut pada
push/PR. Test provider dan alur penerimaan memakai mock, bukan kredensial live.
Untuk memvalidasi Compose tanpa menyalakan layanan: `docker compose config -q`.

Kontrak endpoint/input/output ada di
[backend/README.md](backend/README.md#frontend-api-contract), sehingga tidak
diduplikasi di sini. Schema tersedia pada `/openapi.json`. Untuk menjalankan satu
job sebagai diagnosis: `(cd backend && uv run python -m seoci.worker --once)`.
Retry/cancel dan inspeksi artefak tersedia melalui workbench dan API.

Batas MVP: autentikasi, pembatasan egress, verifikasi fakta mendalam, reservasi biaya
sebelum panggilan model, dan kebijakan retensi/backup lintas aplikasi/checkpoint
masih perlu penguatan. Publishing GitHub bukan pengganti tanggung jawab editor.
