# SEO Content Intelligence

Workbench editorial untuk mengubah satu kata kunci menjadi satu paket artikel SEO
yang dapat ditelusuri sumbernya. Pipeline membantu riset, brief, penulisan, optimasi,
QA dan ekspor. **Manusia tetap menyetujui kata kunci, brief dan artikel akhir.**
Hasil dapat diunduh atau dikirim sebagai pull request ke repositori blog GitHub.

> MVP ini memakai login sederhana berbasis file lokal; semua akun memiliki akses penuh.
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

Setelah API siap, buka **http://localhost:3000** dan buat akun admin pertama.
Di terminal lain, setelah API dan worker siap (seed meminta username/password):

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

Setelah API sehat, buka **http://localhost:3000** untuk membuat admin pertama.
Di terminal lain setelah worker siap (perintah berikut meminta username/password):

```sh
docker compose exec api python seed.py
# Opsional: walkthrough curl sampai ekspor melalui API host pada port 8000
(cd backend && uv sync --frozen --python 3.12 && uv run python demo.py)
```

Compose menjalankan migrasi sebelum API, menunggu PostgreSQL sehat sebelum API,
dan API sehat sebelum worker/web. API/web hanya dipublikasikan pada
`127.0.0.1:8000` dan `127.0.0.1:3000`; PostgreSQL tidak membuka port host.
Web dibangun dengan proxy internal `http://api:8000`. Database dan checkpoint
bertahan di named volume `pgdata`. File akun dan secret sesi otomatis bertahan di
volume `authdata` yang dipasang pada `/app/data` di container API. Jangan hapus
volume ini saat upgrade; `docker compose down -v` juga menghapus akun/secret.

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

## Settings melalui web

Buka **Settings** di sidebar (`/settings`) untuk mengatur LLM, DataForSEO, Serper, Google Search Console dan
GitHub tanpa mengubah environment atau me-restart API/worker. Jalankan
`(cd backend && uv run alembic upgrade head)` saat upgrade; migration `0004`
menambahkan tabel `app_settings` dan audit aplikasi.

Nilai yang tersimpan di database mengungguli environment/Settings. Field yang
belum tersimpan memakai environment lalu default aplikasi. Model LLM kosong
tetap berarti mock; base URL kosong memakai endpoint bawaan LiteLLM. Kunci LLM
tersimpan diteruskan sebagai `api_key`; jika belum ada, aplikasi memakai
`LLM_API_KEY`, lalu `OPENAI_API_KEY` atau `ANTHROPIC_API_KEY` untuk model provider
tersebut. Provider LiteLLM lain tetap dapat memakai environment kredensialnya.
API dan worker membaca ulang konfigurasi saat pemakaian berikutnya. Panggilan
yang sedang berjalan tidak diubah dan hasil provider yang sudah di-cache tetap
mengikuti TTL cache.

Input rahasia selalu kosong saat halaman dimuat. Biarkan kosong untuk menjaga
kunci lama; masukkan nilai baru untuk mengganti. **Clear**, lalu **Save settings**,
menghapus nilai database saja: kunci environment dapat tetap berstatus configured.
Badge membedakan sumber database dan environment; nilai kunci tidak pernah
dikembalikan oleh API. `GET /api/settings` memberi nilai non-rahasia dan metadata
`{configured, source}` untuk rahasia. `PUT /api/settings` menerima update parsial;
field yang dihilangkan tidak berubah dan `null` menghapus override database.
Audit hanya mencatat nama field yang berubah.

**Penting:** semua pengguna yang sudah login dapat mengganti konfigurasi.
Tambahkan hanya akun tepercaya dan batasi akses jaringan. Kunci disimpan sebagai plaintext di
database (bukan dienkripsi), sehingga file/volume database dan backup harus
dilindungi. Write-only berarti kunci tidak ditampilkan kembali, bukan bahwa
penyimpanan database terenkripsi.

### Serper dan Google Search Console

Di Settings, pilih **SERP provider** dan **Keyword data provider** secara terpisah.
Pilihan keyword **Automatic** (nilai kosong) mempertahankan kompatibilitas:
DataForSEO ketika SERP memakai DataForSEO; selain itu mock. Memilih `mock`
secara eksplisit menonaktifkan data keyword live walaupun SERP live.
Contoh kombinasi murah: SERP **Serper** dengan kunci Serper, keyword
**Search Console (own site)** dengan service-account JSON dan properti GSC.
Kedua adapter memakai timeout dan cache jaringan aplikasi; tidak perlu restart.

Untuk GSC, aktifkan Google Search Console API pada proyek Google Cloud, buat
service account dan unduh JSON key. **Tambahkan email service account sebagai
pengguna pada properti Search Console** yang dipilih. Tempel seluruh JSON pada
textarea write-only Settings, bukan nama/path file. JSON harus bertipe
`service_account` dengan `client_email` dan `private_key`; kunci privat harus valid
agar autentikasi berhasil. Aplikasi memakai scope baca-saja
`https://www.googleapis.com/auth/webmasters.readonly`.

GSC mengambil dimensi `query` selama 90 hari kalender sampai kemarin, seluruh
negara/bahasa/perangkat pada properti tersebut (bukan estimasi pasar untuk locale
proyek). Discovery memakai 10 query teratas menurut klik. Mode selected memakai
filter query persis; jika tidak ditemukan, metrik kosong dengan catatan jelas.
Klik, impresi, CTR dan posisi rata-rata disimpan; **search volume tetap `null`**.
Impresi menjadi sinyal demand dengan confidence lebih rendah dan provenance
**Search Console (own site)**. Data beberapa hari terakhir bisa belum lengkap;
properti tanpa query menghentikan discovery dengan pesan yang dapat ditindaklanjuti.
Serper memetakan organic results serta menyimpan people-also-ask dan related
searches dalam snapshot SERP; negara/bahasa mengikuti proyek.

## Login dan akun lokal

Pada kunjungan pertama, aplikasi mengarahkan ke `/setup` (**Create admin account**)
jika file akun belum ada atau kosong. Buat username/password sendiri, lalu login
di `/login`. Setup ditutup setelah akun pertama tersimpan; tidak ada password
bawaan. Lakukan setup sebelum membuka akses jaringan. Semua akun mempunyai hak
yang sama, termasuk pengaturan provider dan publishing; belum ada role/otorisasi
per proyek atau pemulihan password melalui email.

Tambahkan akun atau ganti password melalui terminal server, dari direktori backend:

```sh
cd backend
uv run python -m seoci.auth add-user owner
```

CLI meminta password dua kali dengan `getpass` (bukan argumen command line).
Untuk Compose: `docker compose exec api python -m seoci.auth add-user owner`.
File `AUTH_USERS_FILE` berisi satu `username:pbkdf2_sha256$iterations$salt$hash`
per baris, memakai PBKDF2-HMAC-SHA256 dengan salt acak dan 600.000 iterasi.
Password minimal 8 karakter; username memakai huruf/angka, titik, underscore atau
hyphen (maksimal 64 karakter). File ditulis atomik dengan permission `0600` dan
lock lokal (POSIX/Linux). Perubahan file dibaca tanpa restart. Mengubah password
atau menghapus baris akun membatalkan sesi akun tersebut. Jangan kosongkan/hapus
file akun kecuali memang ingin membuka setup kembali. File rusak gagal tertutup.

`AUTH_SECRET` menandatangani cookie sesi HttpOnly, SameSite=Lax, berlaku 7 hari.
Jika kosong, API membuat secret acak di `<AUTH_USERS_FILE>.secret`, dengan permission
`0600`; backup file ini bersama file akun. Rotasi secret membatalkan semua sesi.
Logout menghapus cookie browser; salinan cookie yang dicuri tetap harus dicabut
melalui penggantian password/secret. Gunakan HTTPS untuk deployment non-lokal;
cookie memakai flag Secure jika request API HTTPS atau proxy terpercaya meneruskan
`X-Forwarded-Proto: https`. Proxy harus menimpa header forwarded dari klien.

API publik hanya `/api/health`, status/setup/login/logout; `/api/auth/me` dan semua
API lainnya memerlukan sesi. `GET /api/auth/status` memberi `setup_required`.
Login gagal dibatasi 5 percobaan per username + IP koneksi selama 15 menit;
limit disimpan per proses dan hilang saat restart, bukan perlindungan brute-force
terdistribusi. Di belakang proxy, IP koneksi dapat sama untuk beberapa pengguna.
Audit setup/login tidak menyimpan password. Next.js meneruskan cookie melalui
rewrite `/api`; browser tidak menyimpan token di localStorage. Seed/demo juga
login melalui API dan menjaga cookie hanya selama proses berjalan.

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
| `AUTH_USERS_FILE` | `./data/auth-users` | File akun relatif terhadap direktori kerja backend; otomatis diabaikan Git di direktori data. Compose memakai `/app/data/auth-users` di volume `authdata`. Jika diganti, pastikan path berada di volume persisten dan jangan commit file tersebut. |
| `AUTH_SECRET` | kosong | Secret penandatangan sesi. Isi secret acak yang panjang (minimal 32 karakter disarankan) atau biarkan API membuat `<AUTH_USERS_FILE>.secret`. Compose meneruskan nilai ini ke backend. |
| `LLM_MODEL` | kosong | Kosong memilih mock; isi identifier LiteLLM seperti `openai/gpt-4o-mini` untuk model nyata. |
| `LLM_API_BASE` | kosong | Opsional: base URL endpoint LLM yang diteruskan sebagai `api_base` ke LiteLLM. Kosong mempertahankan endpoint bawaan provider; Compose meneruskannya ke API dan worker. |
| `LLM_API_KEY` | kosong | Kunci generik opsional, diteruskan sebagai `api_key` ke LiteLLM; dapat diganti lewat Settings. Compose meneruskannya ke API dan worker. |
| `OPENAI_API_KEY` | tidak disetel aplikasi | Kunci OpenAI, dibaca LiteLLM; Compose meneruskan nilai atau string kosong. |
| `ANTHROPIC_API_KEY` | tidak disetel aplikasi | Kunci Anthropic bila identifier LiteLLM memakai provider itu; Compose juga meneruskannya. |
| `SERP_PROVIDER` | `mock` | `mock`, `dataforseo`, atau `serper`; mengendalikan SERP dan penemuan sumber riset. |
| `KEYWORD_PROVIDER` | kosong | `mock`, `dataforseo`, atau `search_console`. Jika kosong/belum diatur, mengikuti perilaku lama: DataForSEO jika SERP memakai DataForSEO; selain itu mock. |
| `SERPER_API_KEY` | kosong | Kunci Serper untuk SERP Google melalui `https://google.serper.dev/search`. |
| `GSC_SERVICE_ACCOUNT_JSON` | kosong | Isi JSON service account lengkap (bukan path file), rahasia. Gunakan JSON satu baris yang dikutip sesuai shell/format `.env`, atau isi melalui Settings. |
| `GSC_SITE_URL` | kosong | Properti Search Console persis seperti terdaftar: `sc-domain:example.com` atau `https://example.com/`; pertahankan trailing slash untuk properti URL-prefix. |
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
| `SERP_PROVIDER=mock` | Mock SERP dan sumber demo; keyword memakai pilihan terpisah, atau mock jika belum dipilih. |
| `SERP_PROVIDER=dataforseo` | SERP DataForSEO nyata; riset sumber mengikuti SERP. Butuh kedua kredensial DataForSEO. Keyword juga DataForSEO hanya jika belum dipilih terpisah. |
| `SERP_PROVIDER=serper` | SERP Serper nyata dengan `SERPER_API_KEY`; keyword tetap mock kecuali dipilih terpisah. |
| `KEYWORD_PROVIDER=dataforseo` | Saran keyword dan volume Google Ads DataForSEO, terlepas dari pilihan SERP. |
| `KEYWORD_PROVIDER=search_console` | Query dan metrik milik properti sendiri dari Google Search Console; bukan volume pencarian pasar. |

Mengisi API key saja tidak mengaktifkan provider nyata. Memilih provider nyata
tanpa kredensial menghasilkan error; tidak ada fallback diam-diam ke mock.
Mode campuran didukung, tetapi LLM nyata dengan SERP mock tetap menerima sumber
demo. Untuk provider LiteLLM lain, ikuti variabel kredensial provider tersebut dan
teruskan secara eksplisit ke proses/container. Tabel di atas mencakup integrasi
yang dipetakan repo, bukan seluruh katalog LiteLLM.

Untuk endpoint OpenAI-compatible, contoh environment proses API dan worker:

```sh
export LLM_MODEL=openai/custom-model
export LLM_API_BASE=http://host:8080/v1
export OPENAI_API_KEY=your-endpoint-key
```

Ganti `custom-model`, host, port dan kunci sesuai endpoint Anda. Kredensial tetap
memakai environment provider (`OPENAI_API_KEY` untuk prefix `openai/`), yang dibaca
LiteLLM juga saat memakai base URL khusus. `LLM_API_KEY` atau kunci yang disimpan
lewat Settings mengungguli kunci environment provider yang dipilih.
Untuk Compose, simpan nilai tersebut di `.env` root atau environment host;
alamat endpoint harus dapat dijangkau dari container API dan worker (bukan
`localhost` host). Mengisi `LLM_API_BASE` tanpa `LLM_MODEL` tetap memilih mock.

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

### Diagnosis provider dan Logs

Kegagalan provider menampilkan kategori, status HTTP (jika tersedia), tahap,
waktu, percobaan, serta petunjuk perbaikan pada halaman run. Setelah memperbaiki
Settings, gunakan **Retry run**. Tombol **Test connection** di Settings hanya
menguji konfigurasi yang sudah disimpan; panggilan live dapat dikenakan biaya.
Mode mock tetap offline. Halaman **Logs** memerlukan login dan menampilkan
maksimal 500 event terbaru dari API maupun worker, dengan filter run dan level.
Pesan diagnosis disensor dan tidak menyimpan respons/error mentah provider.
Logging Python juga mengirim diagnosis tersensor ke stdout container;
gunakan `docker compose logs worker api` untuk inspeksi.

Pembaruan VPS cukup `git pull && docker compose up -d --build`: service API
menjalankan `alembic upgrade head` (termasuk tabel diagnosis migrasi `0005`)
sebelum sehat, lalu worker menggunakan database PostgreSQL yang sama.

Batas MVP: otorisasi per pengguna/proyek, pembatasan egress, verifikasi fakta mendalam, reservasi biaya
sebelum panggilan model, dan kebijakan retensi/backup lintas aplikasi/checkpoint
masih perlu penguatan. Publishing GitHub bukan pengganti tanggung jawab editor.
