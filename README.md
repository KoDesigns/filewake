<p align="center">
  <img src="frontend/static/Logo_Silhuet_invert_Gradient.svg" width="112" alt="Filewake logo" />
</p>

<h1 align="center">Filewake</h1>

<p align="center">
  A private, local and stateless file conversion service.<br />
  Drop files, choose an output, convert, download, and forget everything.
</p>

Filewake combines a minimal drag-and-drop interface with an API for scripts, n8n, agents and other applications. It runs as one hardened Docker container with one port, no database, no cloud conversion service and no persistent file storage.

> Files are converted locally on your server. They are not sent to external conversion services and are removed from temporary server storage after conversion.

## Quick start with Docker

### Requirements

- Docker Engine or Docker Desktop
- Docker Compose V2 (`docker compose`)
- At least 6 GB RAM available to Docker for the default limits

Clone the private repository and start Filewake:

```bash
git clone git@github.com:KoDesigns/filewake.git
cd filewake
docker compose up -d --build
```

Open:

```text
http://localhost:8090
```

Verify the API and packaged conversion engines:

```bash
curl http://127.0.0.1:8090/api/health
```

The first build takes longer because the image packages native media and document engines. Later starts use the built image.

Useful Docker commands:

```bash
# Follow logs
docker compose logs -f converter

# Restart
docker compose restart converter

# Stop and remove the container
docker compose down

# Rebuild after an update
docker compose build --pull
docker compose up -d
```

No database migration, account setup, volume creation or separate frontend service is required.

## Dockge setup

Filewake is a normal Compose stack and can be deployed directly through Dockge:

1. Create a stack named `filewake`.
2. Place this repository in the stack directory.
3. Use the included [`compose.yaml`](compose.yaml).
4. Select **Deploy**.
5. Open `http://SERVER-IP:8090`.

Normal operation uses no persistent Docker volume. `/tmp` and `/run` are writable `tmpfs` mounts; the remainder of the container filesystem is read-only.

## Local development

Local development runs FastAPI and the Svelte frontend separately with one launcher command.

### Requirements

- macOS with Homebrew
- Python 3
- Node.js 24.19.0 or a newer supported Node 24 LTS release

Install the native conversion engines and development dependencies once:

```bash
brew bundle --file Brewfile

python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt

cd frontend
npm ci
cd ..
```

Start both development servers:

```bash
./dev.sh
```

Open the UI at `http://127.0.0.1:5173`. The API runs at `http://127.0.0.1:8080`, and Vite proxies `/api` requests to it. Press `Ctrl+C` once to stop both servers.

Override the ports if they are already in use:

```bash
API_PORT=8081 FRONTEND_PORT=5174 ./dev.sh
```

If the launcher is not executable after downloading the repository:

```bash
chmod +x dev.sh
./dev.sh
```

## API

The browser UI uses the same public API available to scripts and integrations.

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/health` | Check service and engine availability |
| `GET` | `/api/info` | Read Filewake version, limits and capabilities |
| `GET` | `/api/formats` | Get the authoritative conversion matrix |
| `POST` | `/api/inspect` | Detect an uploaded file and list valid outputs |
| `POST` | `/api/convert` | Convert one uploaded file and return the binary result |
| `GET` | `/api/openapi.json` | Download the OpenAPI schema |

### List available conversions

```bash
curl -sS http://127.0.0.1:8090/api/formats | jq
```

The response is generated from the backend registry. The frontend does not maintain a separate format list.

### Inspect a file

```bash
curl -sS \
  -F 'file=@photo.heic' \
  http://127.0.0.1:8090/api/inspect | jq
```

Example response:

```json
{
  "filename": "photo.heic",
  "detected_format": "heic",
  "mime": "image/heic",
  "category": "image",
  "size": 4839201,
  "possible_outputs": ["jpg", "png", "webp", "avif"]
}
```

Filewake checks the filename extension, client MIME type, file signature and parser metadata. A spoofed extension does not choose the conversion engine.

### Convert a file

```bash
curl -fS \
  -F 'file=@photo.heic' \
  -F 'output_format=jpg' \
  http://127.0.0.1:8090/api/convert \
  --output photo.jpg
```

The response is the converted binary with an attachment filename and output MIME type. Helpful response headers include:

```text
X-Input-Format
X-Output-Format
X-Conversion-Engine
X-Original-Size
X-Converted-Size
```

Only `file` and `output_format` are accepted. Filewake does not accept converter arguments, filters, scripts, templates or URLs.

### API errors

Errors use consistent JSON and do not expose raw native-process output:

```json
{
  "error": "unsupported_conversion",
  "message": "This conversion is not supported."
}
```

Common error codes include `unsupported_file`, `unsupported_conversion`, `invalid_file`, `file_too_large`, `conversion_failed`, `conversion_timeout`, `output_too_large`, `temporary_storage_full` and `server_busy`.

### n8n and agents

In n8n, use an **HTTP Request** node with a multipart request:

- `file`: the incoming binary file
- `output_format`: a value returned by `/api/formats` or `/api/inspect`
- response type: file/binary

An agent needs only this flow:

```text
GET /api/formats → POST /api/inspect → POST /api/convert
```

No knowledge of FFmpeg, LibreOffice, libvips, Pandoc or FontTools is required.

## Supported formats

The exact live matrix is always available from `/api/formats`.

| Category | Inputs | Typical outputs |
|---|---|---|
| Images | JPG, PNG, WebP, AVIF, HEIC/HEIF, TIFF | JPG, PNG, WebP, AVIF, TIFF |
| Audio | MP3, WAV, FLAC, AAC, M4A, OGG, Opus, AIFF | Any other allowlisted audio format |
| Video | MP4, MKV, MOV, WebM | MP4, MKV, MOV, WebM |
| Documents | DOCX, ODT, RTF, TXT, Markdown, HTML, EPUB, PPTX, ODP, XLSX, ODS | Explicit allowlisted routes, including PDF output |
| Fonts | TTF, OTF, WOFF, WOFF2 | WOFF/WOFF2 or the recoverable original desktop format |

PDF is output-only. Filewake deliberately does not accept `.designspace`, UFO projects, PostScript, EPS, XPS, URL inputs, uploaded scripts/filters, arbitrary converter options or encrypted-document bypass attempts.

## Configuration

Set values in the Compose environment or Dockge stack editor.

| Variable | Default | Purpose |
|---|---:|---|
| `CONVERTER_PORT` | `8090` | Published host port |
| `MAX_FILE_SIZE_MB` | `2048` | Maximum size of one upload |
| `MAX_BATCH_FILES` | `50` | Frontend batch file limit |
| `MAX_BATCH_SIZE_MB` | `4096` | Frontend combined batch limit |
| `MAX_PARALLEL_CONVERSIONS` | `2` | Maximum concurrent native conversions |
| `MAX_IMAGE_PIXELS` | `100000000` | Decoded image pixel ceiling |
| `MAX_OUTPUT_SIZE_MB` | `4096` | Maximum generated output size |
| `IMAGE_TIMEOUT_SECONDS` | `120` | Image conversion timeout |
| `FONT_TIMEOUT_SECONDS` | `120` | Font conversion timeout |
| `DOCUMENT_TIMEOUT_SECONDS` | `300` | Document conversion timeout |
| `AUDIO_TIMEOUT_SECONDS` | `600` | Audio conversion timeout |
| `VIDEO_TIMEOUT_SECONDS` | `1800` | Video conversion timeout |
| `TMPFS_SIZE` | `4G` | RAM-backed `/tmp` allocation |
| `MEMORY_LIMIT` | `6g` | Container memory limit |
| `CPU_LIMIT` | `4.0` | Container CPU limit |

Example port override:

```bash
CONVERTER_PORT=8091 docker compose up -d
```

Keep `TMPFS_SIZE`, `MEMORY_LIMIT`, upload/output limits and expected concurrency consistent with one another.

## Architecture

```text
Browser / script / agent
          │
          ▼
  FastAPI + static Svelte UI
          │
          ▼
  Validation and registry
          │
          ▼
       Dispatcher
     ┌────┼────────┬────────────┐
     ▼    ▼        ▼            ▼
  libvips FFmpeg LibreOffice FontTools
     │               │
     ▼               ▼
ImageMagick         Pandoc
  fallback
```

The production image contains the frontend and every conversion engine. Node.js exists only in the frontend build stage and is not present as the application server.

## Privacy and storage

Filewake has:

- no accounts
- no database
- no conversion history
- no analytics or telemetry
- no cloud conversion API
- no persistent upload or output directory
- no persistent Docker volume

Each request receives a random workspace below `/tmp/converter`. In Compose, `/tmp` is RAM-backed `tmpfs`. Inputs and outputs are deleted after streaming completes, fails, times out or disconnects. Successful browser results live in temporary browser `Blob` objects and disappear when the page is refreshed or cleared.

The accurate guarantee is **no persistent file storage**. Uploaded bytes necessarily exist temporarily while a conversion is running.

## Security model

Filewake processes arbitrary, potentially malicious binary files. Its defenses are layered:

- strict conversion allowlist
- file signature and MIME inspection
- no shell interpolation or user-controlled command arguments
- bounded upload, output, pixel and multipart limits
- per-engine timeouts
- application-level concurrency limiting
- isolated temporary workspaces and LibreOffice profiles
- sanitized subprocess environments
- restrictive ImageMagick policy
- FFmpeg local-file protocol restrictions and `-nostdin`
- Pandoc sandboxing where supported
- non-root container user (`10001:10001`)
- read-only root filesystem
- all Linux capabilities dropped
- `no-new-privileges`
- writable `tmpfs` only for `/tmp` and `/run`
- immediate cleanup on success, failure and timeout

The recommended deployment target is a trusted LAN or VPN. Do not expose Filewake directly to the public internet without authentication, TLS, rate limiting, reverse-proxy body limits and monitoring.

Container isolation reduces risk but is not a perfect sandbox against every future native-parser or kernel vulnerability. Keep Docker, the host kernel and the Filewake image patched.

## Tests

Run backend and security tests:

```bash
.venv/bin/pytest
```

Run native conversion integration tests:

```bash
.venv/bin/pytest -m integration
```

Validate and build the frontend:

```bash
cd frontend
npm run check
npm run build
```

Run dependency audits:

```bash
.venv/bin/pip-audit -r requirements.txt
cd frontend && npm audit
```

## Image inspection and vulnerability scanning

Inspect packaged versions and the ImageMagick policy:

```bash
docker run --rm --entrypoint cat local/stateless-converter:1.0.0 /app/dependency-versions.txt
docker run --rm --entrypoint magick local/stateless-converter:1.0.0 -list policy
```

Scan the final image with Trivy; Trivy is a deployment tool and is not included in the runtime image:

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

Review every High/Critical result. Do not suppress a finding without understanding whether the affected component is reachable and whether a patched version exists.

## Updating Filewake

Dependencies are not updated inside a running container. The update process is:

1. Review upstream security advisories.
2. Update exact dependency pins, checksums and image digests.
3. Recreate and review lock files.
4. Run unit, integration, security and frontend tests.
5. Rebuild with `docker compose build --pull`.
6. Inspect packaged versions and run a vulnerability scan.
7. Deploy the rebuilt image.

## Troubleshooting

### A conversion engine is unavailable

Check engine discovery:

```bash
curl http://127.0.0.1:8090/api/health
```

For Docker, inspect `/app/dependency-versions.txt`. For local development, install the complete `Brewfile` and restart `./dev.sh`.

### A port is already in use

Docker:

```bash
CONVERTER_PORT=8091 docker compose up -d
```

Local development:

```bash
API_PORT=8081 FRONTEND_PORT=5174 ./dev.sh
```

### Temporary storage is full

Increase `TMPFS_SIZE` and the container memory allocation, or lower file, output and concurrency limits.

### LibreOffice fails on the read-only filesystem

Do not make the root filesystem writable. Verify that `/tmp` is mounted and writable by UID `10001`; Filewake redirects each job's HOME and LibreOffice profile there.

### ImageMagick denies an image

Verify the active policy:

```bash
docker run --rm --entrypoint magick local/stateless-converter:1.0.0 -list policy
```

Do not broaden the policy casually. libvips is the primary raster engine; ImageMagick is a restricted fallback.

### Dockge cannot build the image

The Docker daemon needs outbound build access to official Docker Hub, Debian, upstream project releases, PyPI and npm. Normal runtime conversion does not depend on an external network service.

## Brand assets

Filewake logo variants and generated favicon assets live in [`frontend/static`](frontend/static). The UI automatically selects black or white inverted artwork in the footer based on the saved theme.

## License

MIT. See [`LICENSE`](LICENSE).
