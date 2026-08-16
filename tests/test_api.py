from __future__ import annotations


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.headers["x-content-type-options"] == "nosniff"
    policy = response.headers["content-security-policy"]
    assert "default-src 'self'" in policy
    assert "font-src 'self' blob:" in policy
    assert "media-src 'self' blob:" in policy


def test_info_is_stateless(client):
    payload = client.get("/api/info").json()
    assert payload["stateless"] is True
    assert payload["persistent_storage"] is False
    assert "font" in payload["categories"]


def test_formats_come_from_registry(client):
    payload = client.get("/api/formats").json()["categories"]
    assert "jpg" in payload["image"]["heic"]
    assert "mp3" in payload["audio"]["flac"]
    assert "mp3" in payload["video"]["mp4"]
    assert "wav" in payload["video"]["mov"]
    assert payload["document"]["csv"][0] == "xlsx"
    assert "csv" in payload["document"]["xlsx"]
    assert payload["font"]["ttf"][0] == "woff2"
    assert "designspace" not in payload["font"]


def test_unexpected_form_field_is_rejected(client):
    response = client.post(
        "/api/inspect",
        files={"file": ("x.txt", b"hello", "text/plain")},
        data={"ffmpeg_args": "-dangerous"},
    )
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_file"


def test_non_multipart_is_rejected(client):
    response = client.post("/api/inspect", content=b"file")
    assert response.status_code == 415
