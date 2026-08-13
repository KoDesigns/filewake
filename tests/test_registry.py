from __future__ import annotations

from backend.conversion.registry import registry


def test_registry_contains_v1_categories():
    assert set(registry.categories()) == {"image", "audio", "video", "document", "font"}


def test_pdf_is_not_an_input():
    assert not registry.is_input_format("pdf")


def test_dangerous_formats_absent():
    for file_format in ("designspace", "ufo", "ps", "eps", "xps", "mvg", "msl"):
        assert not registry.is_input_format(file_format)


def test_no_identity_conversions():
    assert all(spec["input"] != spec["output"] for spec in registry.specs())
