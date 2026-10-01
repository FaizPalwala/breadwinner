"""Unit tests for Sprint 4: Voice & Audio Experience and Non-Blocking Recording Session."""

import pytest
from pathlib import Path
from breadwinner.core.audio import (
    AudioRecorder,
    AudioRecordingSession,
    AudioTranscriber,
    AudioBackendInfo
)
from breadwinner.ui.audio_widgets import (
    AudioWaveformWidget,
    AudioVUMeterWidget,
    AudioDictationModal
)


def test_audio_recording_session_mock_lifecycle(tmp_path):
    wav_path = tmp_path / "test_session.wav"
    session = AudioRecorder.create_session(output_wav=wav_path, mock=True)

    assert session.is_recording is False
    assert session.start() is True
    assert session.is_recording is True
    assert session.get_elapsed_seconds() >= 0.0

    success = session.stop()
    assert success is True
    assert session.is_recording is False
    assert wav_path.exists()
    assert wav_path.stat().st_size > 44  # Valid WAV header size


def test_audio_transcriber_backend_detection():
    backend_info = AudioTranscriber.detect_backend()
    assert isinstance(backend_info, AudioBackendInfo)
    assert backend_info.name in ["mlx-whisper", "faster-whisper", "whisper", "groq-whisper", "openai-whisper", "mock"]
    assert backend_info.available is True


def test_audio_transcriber_transcribe_mock(tmp_path):
    wav_path = tmp_path / "test_audio.wav"
    session = AudioRecorder.create_session(output_wav=wav_path, mock=True)
    session.start()
    session.stop()

    transcription = AudioTranscriber.transcribe(wav_path, backend_override="mock")
    assert isinstance(transcription, str)
    assert len(transcription) > 10
    assert "QPS" in transcription or "latency" in transcription


def test_audio_waveform_widget_states():
    widget = AudioWaveformWidget()
    assert widget.state == "idle"

    widget.set_state("recording")
    assert widget.state == "recording"
    widget.advance_frame()
    assert widget.frame == 1

    widget.set_state("transcribing")
    assert widget.state == "transcribing"

    widget.set_state("done")
    assert widget.state == "done"


def test_audio_vu_meter_widget_levels():
    widget = AudioVUMeterWidget()
    assert widget.level == 0.0

    widget.update_level(0.5)
    assert widget.level == 0.5

    widget.update_level(1.0)
    assert widget.level == 1.0


def test_audio_dictation_modal_composition():
    modal = AudioDictationModal(prompt_title="Test Voice Dictation")
    assert modal.prompt_title == "Test Voice Dictation"
    assert modal.backend_info is not None
