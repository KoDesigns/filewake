from __future__ import annotations

from backend.conversion.video import VideoConverter


def test_compatible_streams_remux():
    probe = {"streams": [{"codec_type": "video", "codec_name": "h264"}, {"codec_type": "audio", "codec_name": "aac"}]}
    assert VideoConverter._can_remux(probe, "mp4") is True


def test_incompatible_streams_transcode():
    probe = {"streams": [{"codec_type": "video", "codec_name": "vp9"}, {"codec_type": "audio", "codec_name": "opus"}]}
    assert VideoConverter._can_remux(probe, "mp4") is False
