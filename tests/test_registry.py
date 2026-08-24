from __future__ import annotations

from backend.conversion.registry import AUDIO_FORMATS, registry


def test_registry_contains_v1_categories():
    assert set(registry.categories()) == {"image", "audio", "video", "document", "font"}


def test_pdf_is_not_an_input():
    assert not registry.is_input_format("pdf")


def test_dangerous_formats_absent():
    for file_format in ("designspace", "ufo", "ps", "eps", "xps", "mvg", "msl"):
        assert not registry.is_input_format(file_format)


def test_no_identity_conversions():
    assert all(spec["input"] != spec["output"] for spec in registry.specs())


def test_csv_excel_routes_are_explicitly_allowlisted():
    assert registry.default_output("csv") == "xlsx"
    assert registry.get("csv", "xlsx").engine == "libreoffice"
    assert registry.get("xlsx", "csv").engine == "libreoffice"
    assert registry.get("csv", "ods") is None


def test_epub_defaults_to_pdf_and_keeps_html_available():
    assert registry.default_output("epub") == "pdf"
    assert registry.possible_outputs("epub") == ["pdf", "html", "md"]
    assert registry.get("epub", "pdf").engine == "pandoc"


def test_video_inputs_support_audio_extraction():
    for source in ("mp4", "mkv", "mov", "webm"):
        assert set(AUDIO_FORMATS).issubset(registry.possible_outputs(source))
        assert all(registry.get(source, target).engine == "ffmpeg" for target in AUDIO_FORMATS)
    assert registry.default_output("mov") == "mp4"
    assert registry.default_output("mkv") == "mp4"
    assert registry.possible_outputs("mp4")[:3] == ["mkv", "mov", "webm"]
