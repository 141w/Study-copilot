"""Tests for the TTS (Text-to-Speech) core module."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.core.tts import DEFAULT_VOICE, VOICES, EdgeTTSProvider, get_tts_provider


def test_get_tts_provider_returns_provider():
    provider = get_tts_provider()
    assert isinstance(provider, EdgeTTSProvider)


def test_get_voices_returns_all_groups():
    provider = EdgeTTSProvider()
    voices = provider.get_voices()
    assert "zh-CN" in voices
    assert "en-US" in voices
    assert len(voices["zh-CN"]) > 0
    assert len(voices["en-US"]) > 0


def test_voices_have_required_fields():
    provider = EdgeTTSProvider()
    voices = provider.get_voices()
    for lang, voice_list in voices.items():
        for v in voice_list:
            assert "id" in v
            assert "name" in v
            assert "language" in v
            assert "gender" in v
            assert v["language"] == lang


def test_default_voice_is_chinese():
    assert DEFAULT_VOICE.startswith("zh-CN")


@pytest.mark.asyncio
async def test_generate_speech_empty_text_raises():
    provider = EdgeTTSProvider()
    with pytest.raises(ValueError, match="文本不能为空"):
        await provider.generate_speech("")


@pytest.mark.asyncio
async def test_generate_speech_whitespace_text_raises():
    provider = EdgeTTSProvider()
    with pytest.raises(ValueError, match="文本不能为空"):
        await provider.generate_speech("   ")


@pytest.mark.asyncio
async def test_generate_speech_calls_edge_tts(tmp_path):
    """Test that generate_speech calls edge_tts.Communicate and saves to a file."""
    provider = EdgeTTSProvider()

    # Create a fake audio file to simulate edge-tts output
    fake_audio_path = None

    async def mock_save(path):
        nonlocal fake_audio_path
        fake_audio_path = path
        # Create a fake MP3 file
        with open(path, "wb") as f:
            f.write(b"\xff\xfb\x90\x00" + b"\x00" * 100)  # Fake MP3 header

    mock_communicate = MagicMock()
    mock_communicate.save = mock_save

    with patch("app.core.tts.edge_tts.Communicate", return_value=mock_communicate):
        # Patch TTS_DIR to use tmp_path
        with patch("app.core.tts.TTS_DIR", str(tmp_path)):
            result = await provider.generate_speech(
                "你好世界", voice="zh-CN-XiaoxiaoNeural", speed=1.0
            )

    assert result is not None
    assert result.endswith(".mp3")
    assert os.path.exists(result)
    assert os.path.getsize(result) > 0


@pytest.mark.asyncio
async def test_generate_speech_speed_rate_calculation(tmp_path):
    """Test that speed is correctly converted to rate percentage."""
    provider = EdgeTTSProvider()
    captured_rate = None

    def capture_init(text, voice, rate=""):
        nonlocal captured_rate
        captured_rate = rate
        mock = MagicMock()

        async def save(path):
            with open(path, "wb") as f:
                f.write(b"\x00" * 10)

        mock.save = save
        return mock

    with patch("app.core.tts.edge_tts.Communicate", side_effect=capture_init):
        with patch("app.core.tts.TTS_DIR", str(tmp_path)):
            # speed=1.5 → rate="+50%"
            await provider.generate_speech("测试", speed=1.5)
            assert captured_rate == "+50%"

            # speed=0.5 → rate="-50%"
            await provider.generate_speech("测试", speed=0.5)
            assert captured_rate == "-50%"

            # speed=1.0 → rate="+0%"
            await provider.generate_speech("测试", speed=1.0)
            assert captured_rate == "+0%"
