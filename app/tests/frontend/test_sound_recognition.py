"""Interaction contracts with synthetic WAV; no microphone/model quality claim."""
import base64
import copy
from io import BytesIO
from pathlib import Path
import sys
import wave

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from frontend.providers import api


def wav(seconds=1, rate=16000, channels=1, width=2):
    output = BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(channels)
        audio.setsampwidth(width)
        audio.setframerate(rate)
        audio.writeframes(b"\0" * int(seconds * rate) * channels * width)
    output.name = "sintetico.wav"
    output.size = len(output.getvalue())
    return output


EVENT = {"event_id": "synthetic-audio-1", "source": "yamnet", "label": "incerto", "confidence": .21,
         "model_version": "yamnet-test-contract", "observed_at": "2026-11-11T00:00:00Z",
         "analysis": {"mode": "yamnet", "model_sha256": "test-only", "duration_seconds": 1,
                      "sample_rate": 16000, "latency_ms": 5,
                      "top_classes": [{"label": "Silence", "score": .7}], "warnings": ["Amostra sintética"]}}


@pytest.fixture
def service(monkeypatch):
    state = {"calls": [], "clip": wav(), "events": [], "status": {"available": True, "mode": "yamnet"},
             "result": copy.deepcopy(EVENT)}
    monkeypatch.setattr(st, "audio_input", lambda *a, **kw: state["clip"])
    def get(path):
        return state["events"] if path == "/sound-events" else state["status"]
    def post(path, payload):
        state["calls"].append((path, payload.copy()))
        if state.get("fail"):
            raise api.APIError("Modelo de áudio indisponível.")
        state["events"] = [state["result"]]
        return copy.deepcopy(state["result"])
    monkeypatch.setattr(api, "get", get)
    monkeypatch.setattr(api, "post", post)
    return state


def page():
    def render():
        from frontend.features.integrations import render_sound
        render_sound()
    return AppTest.from_function(render, default_timeout=15).run()


def analyze_button(at):
    buttons = [button for button in at.button if button.label == "Analisar áudio"]
    assert buttons, "A tela deve oferecer análise real por ação explícita."
    return buttons[0]


def test_recording_preview_does_not_analyze_without_click(service):
    at = page()
    assert not at.exception
    analyze_button(at)
    assert len(at.get("audio")) == 1
    assert not service["calls"]
    at.checkbox[0].check().run()
    assert not service["calls"]
    analyze_button(at).click().run()
    assert not at.exception
    assert service["calls"][0][0] == "/audio/analyze"
    assert base64.b64decode(service["calls"][0][1]["audio_base64"]) == service["clip"].getvalue()
    assert any("Incerto" in value.value for value in at.markdown)
    assert any("Amostra sintética" in value.value for value in at.warning)
    assert at.dataframe[0].value["Classe"].tolist() == ["Silence"]
    assert at.dataframe[1].value["Origem"].tolist() == ["YAMNet (análise no servidor)"]
    assert at.dataframe[1].value["ID do evento"].tolist() == ["synthetic-audio-1"]


def test_retry_after_failure_uses_same_uuid_and_never_manual_fallback(service):
    service["fail"] = True
    at = page()
    analyze_button(at)
    at.checkbox[0].check()
    analyze_button(at).click().run()
    assert at.error
    service["fail"] = False
    analyze_button(at).click().run()
    assert not at.exception
    first, retry = [payload for _, payload in service["calls"]]
    assert first["client_request_id"] == retry["client_request_id"]
    service["clip"] = wav(seconds=2)
    at.run()
    analyze_button(at).click().run()
    assert service["calls"][-1][1]["client_request_id"] != first["client_request_id"]
    assert all(path == "/audio/analyze" for path, _ in service["calls"])


@pytest.mark.parametrize("clip", [None, BytesIO(b"not WAV"), wav(seconds=.5), wav(seconds=16),
                                  wav(width=1), wav(channels=3), wav(rate=6000), BytesIO(b"x" * 3_000_001)])
def test_invalid_recording_never_reaches_service(service, clip):
    service["clip"] = clip
    at = page()
    analyze_button(at)
    at.checkbox[0].check()
    analyze_button(at).click().run()
    assert not at.exception
    assert at.error
    assert not service["calls"]


def test_audio_service_503_is_safe_and_explicit(monkeypatch):
    class Response:
        status_code = 503
    monkeypatch.setattr(api.requests, "request", lambda *a, **kw: Response())
    with pytest.raises(api.APIError, match="áudio.*indisponível"):
        api.post("/audio/analyze", {"audio_base64": "synthetic"})


def test_uploaded_stereo_wav_requires_consent_then_is_analyzed(service, monkeypatch):
    from frontend.features import sound_recognition
    uploaded = wav(seconds=1, rate=48000, channels=2)
    monkeypatch.setattr(sound_recognition, "file_picker", lambda *a, **kw: uploaded if kw["key"] == "yamnet_wav" else None)
    at = page()
    at.radio[0].set_value("Enviar arquivo WAV").run()
    assert not service["calls"]
    assert len(at.get("audio")) == 1
    analyze_button(at).click().run()
    assert at.error and not service["calls"]
    at.checkbox[0].check()
    analyze_button(at).click().run()
    assert not at.exception
    assert base64.b64decode(service["calls"][0][1]["audio_base64"]) == uploaded.getvalue()


def test_incomplete_or_manual_response_is_not_presented_as_inference(service, monkeypatch):
    monkeypatch.setattr(api, "post", lambda *a, **kw: {"event_id": "fake", "source": "manual", "label": "campainha"})
    at = page()
    at.checkbox[0].check()
    analyze_button(at).click().run()
    assert not at.exception
    assert any("incompleta" in error.value for error in at.error)
    assert not at.dataframe


def test_temporal_event_displays_windows_and_separate_clip_means(service):
    service["result"].update(label="batida", confidence=.8)
    service["result"]["analysis"].update(
        decision_version="temporal-v1", aggregation="target_event_windows",
        event_windows=[{"start_seconds": .48, "end_seconds": 1.44, "label": "batida", "score": .8}],
        top_classes=[{"label": "Knock", "score": .8}],
        mean_top_classes=[{"label": "Knock", "score": .285}])
    at = page()
    at.checkbox[0].check()
    analyze_button(at).click().run()
    assert not at.exception
    assert any("Evento em trecho" in value.value for value in at.markdown)
    windows = next(table.value for table in at.dataframe if "Início (s)" in table.value.columns)
    assert windows["Início (s)"].tolist() == [.48]
    assert windows["Fim (s)"].tolist() == [1.44]
    assert any(expander.label == "Médias do clipe completo" for expander in at.expander)
    scores = [table.value["Escore"].tolist() for table in at.dataframe if "Classe" in table.value.columns]
    assert scores == [[.8], [.285]]
    assert any("temporal-v1" in value.value for value in at.caption)


@pytest.mark.parametrize("changed_field", ["model_version", "decision_version", "source_profile_version"])
def test_same_audio_gets_new_identity_after_model_or_decision_change(service, changed_field):
    service["status"].update(model_version="model-v1", decision_version="temporal-v1")
    at = page()
    at.checkbox[0].check()
    analyze_button(at).click().run()
    first = service["calls"][-1][1]["client_request_id"]
    analyze_button(at).click().run()
    assert service["calls"][-1][1]["client_request_id"] == first
    service["status"][changed_field] = "v2"
    at.run()
    assert not any(value.value == "Resultado da análise" for value in at.subheader)
    analyze_button(at).click().run()
    assert not at.exception
    assert service["calls"][-1][1]["client_request_id"] != first


def test_neighborhood_source_shown_and_carried_into_report_draft(service):
    service['result']['analysis']['neighborhood_source'] = {
        'label': 'furadeira', 'score': .8, 'model_class': 'Drill',
        'version': 'neighborhood-v1', 'aggregation': 'clip_mean'}
    at = page()
    at.checkbox[0].check()
    analyze_button(at).click().run()
    assert not at.exception
    assert any('Furadeira' in x.value for x in at.markdown)
    assert any('0.800' in x.value for x in at.caption)
    next(button for button in at.button if button.label == 'Criar relato com esta análise').click().run()
    assert at.session_state['draft_sound_event']['analysis']['neighborhood_source']['label'] == 'furadeira'
