# syntax=docker/dockerfile:1.7
FROM node:24.19.0-bookworm-slim@sha256:3638d9a6fe4030bd716be989438248074489337ba3275657f93595428be4fc03 AS frontend-build
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --ignore-scripts --no-audit
COPY frontend/ ./
RUN npm run check && npm run build

FROM python:3.13.14-slim-trixie@sha256:9662417aace5ae7b8e2609cce472b72a8958e134ba372808abe9cc1a0c0125e6 AS vips-build
ARG VIPS_VERSION=8.18.2
ARG VIPS_SHA256=a30d4aede16f1c2899c1a2241870f8a7409feafa38484bcdcdac113d6d6f8ff5
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential ca-certificates curl meson ninja-build pkg-config xz-utils \
      libexpat1-dev libglib2.0-dev libheif-dev libimagequant-dev libjpeg62-turbo-dev \
      liborc-0.4-dev libpng-dev libtiff-dev libwebp-dev \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /build
RUN curl -fsSLo vips.tar.xz "https://github.com/libvips/libvips/releases/download/v${VIPS_VERSION}/vips-${VIPS_VERSION}.tar.xz" \
    && echo "${VIPS_SHA256}  vips.tar.xz" | sha256sum -c - \
    && tar -xJf vips.tar.xz \
    && meson setup vips-build "vips-${VIPS_VERSION}" --buildtype=release --prefix=/opt/vips --libdir=lib \
    && meson compile -C vips-build \
    && meson install -C vips-build

FROM python:3.13.14-slim-trixie@sha256:9662417aace5ae7b8e2609cce472b72a8958e134ba372808abe9cc1a0c0125e6 AS ffmpeg-build
ARG FFMPEG_VERSION=8.1.2
ARG FFMPEG_SHA256=464beb5e7bf0c311e68b45ae2f04e9cc2af88851abb4082231742a74d97b524c
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential ca-certificates curl nasm pkg-config xz-utils yasm \
      libmp3lame-dev libopus-dev libvorbis-dev libvpx-dev libx264-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /build
RUN curl -fsSLo ffmpeg.tar.xz "https://ffmpeg.org/releases/ffmpeg-${FFMPEG_VERSION}.tar.xz" \
    && echo "${FFMPEG_SHA256}  ffmpeg.tar.xz" | sha256sum -c - \
    && tar -xJf ffmpeg.tar.xz \
    && cd "ffmpeg-${FFMPEG_VERSION}" \
    && ./configure \
         --prefix=/opt/ffmpeg \
         --libdir=/opt/ffmpeg/lib \
         --disable-debug \
         --disable-doc \
         --disable-ffplay \
         --enable-gpl \
         --enable-shared \
         --enable-libmp3lame \
         --enable-libopus \
         --enable-libvorbis \
         --enable-libvpx \
         --enable-libx264 \
    && make -j2 \
    && make install

FROM python:3.13.14-slim-trixie@sha256:9662417aace5ae7b8e2609cce472b72a8958e134ba372808abe9cc1a0c0125e6 AS imagemagick-build
ARG IMAGEMAGICK_VERSION=7.1.2-28
ARG IMAGEMAGICK_SHA256=dccafd60d255f4369728d1f7ae3d2d41f2615dad5490d697398b1010e68c02d2
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential ca-certificates curl pkg-config xz-utils \
      libheif-dev libjpeg62-turbo-dev libpng-dev libtiff-dev libwebp-dev \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /build
RUN curl -fsSLo imagemagick.tar.xz "https://download.imagemagick.org/archive/releases/ImageMagick-${IMAGEMAGICK_VERSION}.tar.xz" \
    && echo "${IMAGEMAGICK_SHA256}  imagemagick.tar.xz" | sha256sum -c - \
    && tar -xJf imagemagick.tar.xz \
    && cd "ImageMagick-${IMAGEMAGICK_VERSION}" \
    && ./configure \
         --prefix=/opt/imagemagick \
         --libdir=/opt/imagemagick/lib \
         --disable-deprecated \
         --disable-docs \
         --disable-static \
         --without-autotrace \
         --without-djvu \
         --without-fftw \
         --without-fontconfig \
         --without-freetype \
         --without-gslib \
         --without-gvc \
         --without-jbig \
         --without-jxl \
         --without-lcms \
         --without-lqr \
         --without-openexr \
         --without-pango \
         --without-raw \
         --without-svg \
         --without-xml \
         --without-x \
    && make -j2 \
    && make install

FROM python:3.13.14-slim-trixie@sha256:9662417aace5ae7b8e2609cce472b72a8958e134ba372808abe9cc1a0c0125e6 AS runtime
ARG TARGETARCH
ARG LIBREOFFICE_VERSION=26.2.5
ARG PANDOC_VERSION=3.10.1
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOME=/tmp \
    TMPDIR=/tmp \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    MAGICK_CONFIGURE_PATH=/etc/ImageMagick-7 \
    PATH=/opt/imagemagick/bin:/opt/ffmpeg/bin:/opt/vips/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl libmagic1 \
      fonts-dejavu-core fonts-liberation libgl1 libsm6 libxinerama1 libxrender1 \
      libfontconfig1 libfreetype6 libexpat1-dev libglib2.0-dev libheif-dev \
      libimagequant-dev libjpeg62-turbo-dev liborc-0.4-dev libpng-dev libtiff-dev libwebp-dev \
      libmp3lame-dev libopus-dev libvorbis-dev libvpx-dev libx264-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Debian's Pandoc 3.1.11 cannot create DOCX while sandboxed. Install the pinned
# upstream static build, which also avoids external runtime data dependencies.
RUN set -eu; \
    if [ -z "${TARGETARCH}" ]; then TARGETARCH="$(dpkg --print-architecture)"; fi; \
    case "${TARGETARCH}" in \
      amd64) pandoc_arch="amd64"; pandoc_sha="72948bf5784f560d5ad1876709daca27e0667f262da727bb33f77b58e52df2f5" ;; \
      arm64) pandoc_arch="arm64"; pandoc_sha="cd3963da375793a4804c65ae538b4f7b9c23f87cac7f6c74a1cf5e2fff7e8d59" ;; \
      *) echo "Unsupported architecture: ${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    pandoc_archive="pandoc-${PANDOC_VERSION}-linux-${pandoc_arch}.tar.gz"; \
    curl -fsSLo "/tmp/${pandoc_archive}" \
      "https://github.com/jgm/pandoc/releases/download/${PANDOC_VERSION}/${pandoc_archive}"; \
    echo "${pandoc_sha}  /tmp/${pandoc_archive}" | sha256sum -c -; \
    tar -xzf "/tmp/${pandoc_archive}" -C /usr/local --strip-components=1; \
    rm "/tmp/${pandoc_archive}"; \
    test "$(pandoc --version | head -n 1)" = "pandoc ${PANDOC_VERSION}"; \
    pandoc --sandbox --from commonmark --to docx \
         --output /tmp/pandoc-sandbox-check.docx /dev/null; \
    test -s /tmp/pandoc-sandbox-check.docx; \
    rm /tmp/pandoc-sandbox-check.docx

RUN set -eu; \
    if [ -z "${TARGETARCH}" ]; then TARGETARCH="$(dpkg --print-architecture)"; fi; \
    case "${TARGETARCH}" in \
      amd64) lo_arch="x86_64"; lo_file="LibreOffice_${LIBREOFFICE_VERSION}_Linux_x86-64_deb.tar.gz"; lo_sha="2f03bfb2ac9f33ea7c77331b4b7a23300fb0ed7443566046bf8b5bc51c1bed1e" ;; \
      arm64) lo_arch="aarch64"; lo_file="LibreOffice_${LIBREOFFICE_VERSION}_Linux_aarch64_deb.tar.gz"; lo_sha="0e72aa19d216f54100389b8b7840e2d1212470d88fddddb1dae9993d06d7e4ec" ;; \
      *) echo "Unsupported architecture: ${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    curl -fsSLo "/tmp/${lo_file}" "https://download.documentfoundation.org/libreoffice/stable/${LIBREOFFICE_VERSION}/deb/${lo_arch}/${lo_file}"; \
    echo "${lo_sha}  /tmp/${lo_file}" | sha256sum -c -; \
    mkdir /tmp/libreoffice; \
    tar -xzf "/tmp/${lo_file}" -C /tmp/libreoffice --strip-components=1; \
    apt-get update; \
    apt-get install -y --no-install-recommends /tmp/libreoffice/DEBS/*.deb; \
    lo_binary="$(find /opt -path '*/program/soffice' -type f -print -quit)"; \
    test -n "${lo_binary}"; \
    ln -s "${lo_binary}" /usr/local/bin/libreoffice; \
    rm -rf /tmp/libreoffice "/tmp/${lo_file}" /var/lib/apt/lists/*

COPY --from=vips-build /opt/vips/ /opt/vips/
COPY --from=ffmpeg-build /opt/ffmpeg/ /opt/ffmpeg/
COPY --from=imagemagick-build /opt/imagemagick/ /opt/imagemagick/
RUN echo '/opt/vips/lib' > /etc/ld.so.conf.d/converter-libs.conf \
    && echo '/opt/ffmpeg/lib' >> /etc/ld.so.conf.d/converter-libs.conf \
    && echo '/opt/imagemagick/lib' >> /etc/ld.so.conf.d/converter-libs.conf \
    && ldconfig \
    && test "$(vips --version | sed 's/^vips-//')" = "8.18.2" \
    && ffmpeg -version | head -n 1 | grep -q 'ffmpeg version 8.1.2' \
    && magick -version | head -n 1 | grep -q 'ImageMagick 7.1.2-28'

WORKDIR /app
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt \
    && python -m pip check \
    && python -c "import starlette; assert tuple(map(int, starlette.__version__.split('.'))) >= (1, 3, 1)" \
    && python -c "import fontTools; assert tuple(map(int, fontTools.__version__.split('.'))) >= (4, 60, 2)"

COPY backend/ ./backend/
COPY config/policy.xml /etc/ImageMagick-7/policy.xml
COPY --from=frontend-build /build/frontend/dist/ ./backend/static/

RUN groupadd --gid 10001 converter \
    && useradd --uid 10001 --gid converter --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin converter \
    && mkdir -p /tmp/converter /run/converter \
    && chown -R converter:converter /tmp/converter /run/converter \
    && magick -list policy | grep -q '/etc/ImageMagick-7/policy.xml' \
    && { \
         echo "Build dependency report"; \
         date -u +%Y-%m-%dT%H:%M:%SZ; \
         ffmpeg -version | head -n 1; \
         ffprobe -version | head -n 1; \
         vips --version; \
         magick -version | head -n 1; \
         libreoffice --version; \
         pandoc --version | head -n 1; \
         python -c "import fastapi,starlette,fontTools; print('FastAPI',fastapi.__version__); print('Starlette',starlette.__version__); print('FontTools',fontTools.__version__)"; \
       } > /app/dependency-versions.txt

USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import json,urllib.request; assert json.load(urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=2))['status']=='ok'"]
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1", "--no-access-log", "--proxy-headers", "--forwarded-allow-ips", "127.0.0.1"]
