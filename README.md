<p align="center">
  <img src="frontend/static/Logo_Silhuet_invert_Gradient.svg" width="116" alt="Filewake logo" />
</p>

<h1 align="center">Filewake</h1>

<p align="center">
  Drop files. Pick an output. Download. Done.
</p>

<p align="center">
  <a href="https://github.com/KoDesigns/filewake/blob/main/LICENSE"><img alt="MIT license" src="https://img.shields.io/github/license/KoDesigns/filewake?style=flat-square&color=005bd0" /></a>
  <a href="https://github.com/KoDesigns/filewake/commits/main"><img alt="Last commit" src="https://img.shields.io/github/last-commit/KoDesigns/filewake?style=flat-square&logo=github&color=005bd0" /></a>
  <img alt="Docker" src="https://img.shields.io/badge/Docker-one_container-005bd0?style=flat-square&logo=docker&logoColor=white" />
  <img alt="Svelte" src="https://img.shields.io/badge/Svelte-static_UI-ff3e00?style=flat-square&logo=svelte&logoColor=white" />
  <img alt="Python" src="https://img.shields.io/badge/Python-FastAPI-3776ab?style=flat-square&logo=python&logoColor=white" />
</p>

Filewake is a local, stateless file converter with a drag-and-drop UI and a small HTTP API.

<i><b>Disclaimer:</b> This is "vibecoded" for personal usage, but feel free to use. Do not take responsibility if something is not working on your system</i>

One container. One port. No accounts, database, history, cloud converter, telemetry, or persistent file storage.

> Files are processed locally on your server, held only in temporary storage while needed, then removed. Browser previews and downloads disappear when the page is refreshed or cleared.

## Run it

You need Docker Compose V2 and about 6 GB of memory with the default limits.

```bash
git clone https://github.com/KoDesigns/filewake.git
cd filewake
docker compose up -d --build
```

Open [http://localhost:8090](http://localhost:8090), or replace `localhost` with your server's LAN address.

Check it:

```bash
curl -fsS http://127.0.0.1:8090/api/health
docker compose ps
```

The first build compiles FFmpeg, libvips, and ImageMagick. A home server may need 10–30 minutes. Completed stages are cached, so later starts and most rebuilds are much faster.

## Dockge

Dockge normally watches `/opt/stacks`. Put Filewake there:

```bash
sudo mkdir -p /opt/stacks/filewake
sudo chown "$USER":"$(id -gn)" /opt/stacks/filewake
git clone https://github.com/KoDesigns/filewake.git /opt/stacks/filewake
cd /opt/stacks/filewake
docker compose config
```

In Dockge, open the top-right menu and select **Scan Stacks Folder**. Open `filewake`, press **Deploy**, then visit:

```text
http://SERVER-IP:8090
```

`docker compose ps` should show `8090->8080`, not only `8080/tcp`.

No setup wizard. No database migration. No volume creation.

## What it converts

The live source of truth is [`GET /api/formats`](#api).

| Type | Inputs | Outputs |
|---|---|---|
| Images | JPG, PNG, WebP, AVIF, HEIC/HEIF, TIFF | JPG, PNG, WebP, AVIF, TIFF |
| Audio | MP3, WAV, FLAC, AAC, M4A, OGG, Opus, AIFF | Other allowlisted audio formats |
| Video | MP4, MKV, MOV, WebM | MP4, MKV, MOV, WebM |
| Documents | DOCX, ODT, RTF, TXT, Markdown, HTML, EPUB, PPTX, ODP, XLSX, ODS, CSV | Explicit allowlisted routes, including PDF and CSV ↔ XLSX |
| Fonts | TTF, OTF, WOFF, WOFF2 | WOFF/WOFF2 or the recoverable desktop format |

PDF is output-only. CSV uses UTF-8 and comma-separated output. CSV → XLSX keeps formula-like values as text. XLSX → CSV exports the first worksheet because CSV cannot hold multiple sheets.

## API

The UI uses the same API available to scripts, n8n, and agents.

| Method | Endpoint | Does what |
|---|---|---|
| `GET` | `/api/health` | Engine availability |
| `GET` | `/api/info` | Version and limits |
| `GET` | `/api/formats` | Conversion matrix |
| `POST` | `/api/inspect` | Detect a file and list valid outputs |
| `POST` | `/api/convert` | Convert one file and return it |
| `GET` | `/api/openapi.json` | OpenAPI schema |

Inspect:

```bash
curl -sS \
  -F 'file=@photo.heic' \
  http://127.0.0.1:8090/api/inspect | jq
```

Convert:

```bash
curl -fS \
  -F 'file=@photo.heic' \
  -F 'output_format=jpg' \
  http://127.0.0.1:8090/api/convert \
  --output photo.jpg
```

Only `file` and `output_format` are accepted. There are no endpoints for URLs, converter arguments, filters, scripts, or templates.

For n8n, send a multipart HTTP request with `file` and `output_format`, then receive the response as binary. An agent only needs:

```text
GET /api/formats → POST /api/inspect → POST /api/convert
```

## How it works

```text
Browser / script
       │
       ▼
FastAPI + static Svelte UI
       │
       ▼
Detection → allowlist → dispatcher
       │
       ├── libvips / restricted ImageMagick
       ├── FFmpeg / ffprobe
       ├── LibreOffice / Pandoc
       └── FontTools
```

Svelte is compiled during the image build. FastAPI/Uvicorn serves both the static UI and `/api/*`. Node is not present at runtime.

Each request gets its own random workspace under `/tmp/converter`. Compose mounts `/tmp` in RAM. The root filesystem stays read-only and there are no persistent volumes.

## Security

Filewake treats every upload as hostile.

- strict format and conversion allowlist
- extension, MIME, signature, and parser checks
- no shell interpolation or user-supplied converter arguments
- upload, output, pixel, multipart, concurrency, and timeout limits
- isolated workspaces and LibreOffice profiles
- minimal subprocess environments
- restrictive ImageMagick policy
- FFmpeg protocol restrictions and `-nostdin`
- Pandoc sandboxing where supported
- non-root UID `10001`
- read-only root filesystem
- all Linux capabilities dropped
- `no-new-privileges`
- writable `tmpfs` only for `/tmp` and `/run`
- cleanup after success, failure, timeout, and disconnect

Use it on a trusted LAN or VPN. Do not put it directly on the public internet without authentication, TLS, rate limiting, reverse-proxy body limits, and monitoring. Containers reduce risk; they are not magic.

<details>
<summary><strong>Configuration</strong></summary>

Set these in Compose, a `.env` file, or Dockge's stack editor.

| Variable | Default | Purpose |
|---|---:|---|
| `CONVERTER_PORT` | `8090` | Host port |
| `MAX_FILE_SIZE_MB` | `2048` | Per-file upload limit |
| `MAX_BATCH_FILES` | `50` | Browser batch count |
| `MAX_BATCH_SIZE_MB` | `4096` | Browser batch size |
| `MAX_PARALLEL_CONVERSIONS` | `2` | Concurrent native jobs |
| `MAX_IMAGE_PIXELS` | `100000000` | Decoded image ceiling |
| `MAX_OUTPUT_SIZE_MB` | `4096` | Generated output ceiling |
| `IMAGE_TIMEOUT_SECONDS` | `120` | Image timeout |
| `FONT_TIMEOUT_SECONDS` | `120` | Font timeout |
| `DOCUMENT_TIMEOUT_SECONDS` | `300` | Document timeout |
| `AUDIO_TIMEOUT_SECONDS` | `600` | Audio timeout |
| `VIDEO_TIMEOUT_SECONDS` | `1800` | Video timeout |
| `TMPFS_SIZE` | `4G` | RAM-backed temporary space |
| `MEMORY_LIMIT` | `6g` | Container memory limit |
| `CPU_LIMIT` | `4.0` | Container CPU limit |

Example:

```bash
CONVERTER_PORT=8091 docker compose up -d
```

Keep the tmpfs, memory, upload, output, and concurrency limits sensible relative to one another.

</details>

<details>
<summary><strong>Local development</strong></summary>

The included launcher starts FastAPI and Vite together on macOS.

```bash
brew bundle --file Brewfile

python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt

cd frontend
npm ci
cd ..

chmod +x dev.sh
./dev.sh
```

Open [http://127.0.0.1:5173](http://127.0.0.1:5173). The API runs on port `8080`, and Vite proxies `/api` to it.

Override either port when needed:

```bash
API_PORT=8081 FRONTEND_PORT=5174 ./dev.sh
```

</details>

<details>
<summary><strong>Tests, versions, and image scanning</strong></summary>

```bash
# Backend and security tests
.venv/bin/pytest -m 'not integration'

# Native conversion tests
.venv/bin/pytest -m integration

# Frontend
cd frontend
npm run check
npm run build
```

Inspect the packaged versions and ImageMagick policy:

```bash
docker run --rm --entrypoint cat local/stateless-converter:1.0.0 /app/dependency-versions.txt
docker run --rm --entrypoint magick local/stateless-converter:1.0.0 -list policy
```

Scan the final image outside the runtime container:

```bash
trivy image \
  --severity HIGH,CRITICAL \
  --ignore-unfixed=false \
  --exit-code 1 \
  local/stateless-converter:1.0.0

trivy image \
  --format cyclonedx \
  --output filewake-sbom.json \
  local/stateless-converter:1.0.0
```

Review findings instead of blindly suppressing them.

</details>

## Update

```bash
cd /opt/stacks/filewake
git pull --ff-only
docker compose up -d --build
```

Updates happen by rebuilding the image. Nothing updates itself inside the running container.

## Known limits

- PDF is an output format, not a promise of perfect editable reconstruction.
- Office conversions can change layout when the source depends on unavailable fonts or platform-specific behavior.
- XLSX → CSV exports one worksheet.
- Font projects such as `.designspace` and UFO are not supported.
- PostScript, EPS, XPS, arbitrary URLs, macros, uploaded filters, and custom converter arguments are not supported.
- Very large browser downloads and browser-created ZIP files still depend on available client memory.

<details>
<summary><strong>Troubleshooting</strong></summary>

Check the stack first:

```bash
docker compose ps
docker compose logs --tail=150 converter
curl -fsS http://127.0.0.1:8090/api/health
```

If the container is healthy but the browser says connection refused, `docker compose ps` must show `8090->8080`. Confirm the binding:

```bash
docker compose config | grep -A5 -B2 'ports:'
sudo ss -ltnp | grep ':8090'
docker compose down
docker compose up -d
```

Do not change Filewake's dedicated bridge network to `internal: true`; Docker cannot publish the application port from a container attached only to an internal network.

If an engine is unavailable, inspect the packaged report:

```bash
docker run --rm --entrypoint cat local/stateless-converter:1.0.0 /app/dependency-versions.txt
```

If ImageMagick rejects a file, inspect the active policy rather than broadening it blindly:

```bash
docker run --rm --entrypoint magick local/stateless-converter:1.0.0 -list policy
```

If `/tmp` fills up, increase `TMPFS_SIZE` and available container memory, or lower the file, output, and concurrency limits.

</details>

## License

[MIT](LICENSE). Filewake is made by [KoDesigns](https://github.com/KoDesigns).
