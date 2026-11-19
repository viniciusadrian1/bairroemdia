"""UI contract tests with a fake backend. Not evidence of real model accuracy."""
import copy
import sys
from pathlib import Path

import pytest
import requests
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = ROOT
sys.path.insert(0, str(APP_ROOT))
from frontend.providers import api
from frontend.features.dashboard import filter_reports


REPORT = {
    "id": "synthetic-report-01", "description": "Relato sonoro sintético no bairro de demonstração.",
    "neighborhood": "Bairro de teste", "latitude": -23.55, "longitude": -46.63,
    "location_confirmed": True, "category": "sound", "status": "pending_review",
    "created_at": "2026-11-10T12:00:00Z", "analysis": {
        "summary": "Relato para revisão humana.", "suggested_category": "sound",
        "confidence": None, "mode": "rules", "warnings": []},
    "vision": None, "guidance": {"answer": "Confira a localização antes de prosseguir.",
        "sources": [], "abstained": False, "mode": "extractive", "warnings": []},
    "review": None, "protocol": None,
}


@pytest.fixture
def backend(monkeypatch):
    state = {"reports": [], "calls": []}

    def get(path):
        if path == "/reports":
            return copy.deepcopy(state["reports"])
        if path == "/integrations":
            return [{"discipline": "IoT", "mode": "arquivo", "status": "parcial", "evidence": [], "pending": "Teste móvel"}]
        if path == "/sound-events":
            return []
        return {"status": "ok", "llm_mode": "extractive", "vision_mode": "unavailable"}

    def post(path, payload=None):
        state["calls"].append((path, copy.deepcopy(payload)))
        if path == "/reports":
            report = copy.deepcopy(REPORT)
            report.update(payload)
            state["reports"].append(report)
            return copy.deepcopy(report)
        if path == "/assistant":
            return copy.deepcopy(REPORT["guidance"])
        report = state["reports"][0]
        if path.endswith("/review"):
            report["status"] = "approved" if payload["approved"] else "rejected"
            report["category"] = payload["corrected_category"]
            report["review"] = payload
        elif path.endswith("/protocol"):
            assert report["status"] == "approved"
            report["status"] = "protocolled"
            report["protocol"] = "DEMO-0001"
        elif path.endswith("/status"):
            report["status"] = payload["status"]
        return copy.deepcopy(report)

    monkeypatch.setattr(api, "get", get)
    monkeypatch.setattr(api, "post", post)
    api.health.clear()
    yield state
    api.health.clear()


def app():
    at = AppTest.from_file(str(APP_ROOT / "frontend" / "app.py"), default_timeout=15).run()
    button(at, "Entrar no bairro").click().run()
    at.radio[0].set_value("Registrar ocorrência").run()
    return at


def button(at, label):
    return next(x for x in at.button if x.label == label)


def test_welcome_enters_once_and_preserves_navigation(backend):
    at = AppTest.from_file(str(APP_ROOT / "frontend" / "app.py"), default_timeout=15).run()
    assert not at.exception
    assert len(at.radio) == 0
    assert backend["calls"] == []
    button(at, "Entrar no bairro").click().run()
    assert not at.exception
    assert at.session_state["brand_entered"] is True
    assert at.radio[0].value == "Início"
    button(at, "Conversar com o agente").click().run()
    assert at.radio[0].value == "Agente do bairro"
    assert not at.exception
    assert not any(b.label == "Entrar no bairro" for b in at.button)
    assert len(at.chat_input) == 1


def test_empty_form_does_not_call_backend(backend):
    at = app()
    button(at, "Analisar relato").click().run()
    assert not at.exception
    assert len(at.error) >= 4
    assert backend["calls"] == []


def test_photo_is_recovered_in_each_new_session(backend, monkeypatch):
    from io import BytesIO
    from PIL import Image
    photo = BytesIO()
    Image.new("RGB", (32, 32), "gray").save(photo, format="JPEG")
    report = copy.deepcopy(REPORT)
    report.update(category="pothole", image_available=True,
                  vision={"mode": "unavailable", "detections": [], "warnings": [], "latency_ms": 0})
    backend["reports"] = [report]
    calls = []
    monkeypatch.setattr(api, "get_image", lambda rid: calls.append(rid) or photo.getvalue())
    for _ in range(2):
        at = app()
        at.radio[0].set_value("Acompanhar e revisar").run()
        assert not at.exception
        assert [tab.label for tab in at.tabs] == ["Foto para revisão", "Resultado do detector"]
        assert at.session_state["report_photos"][report["id"]] == photo.getvalue()
        at.run()
    assert calls == [report["id"], report["id"]]


def test_timeout_retry_reuses_identity_and_new_report_resets(backend, monkeypatch):
    original = api.post
    attempts = []
    def post(path, payload=None):
        if path == "/reports":
            attempts.append(payload.copy())
            if len(attempts) == 1:
                raise api.APIError("O serviço demorou para responder.")
        return original(path, payload)
    monkeypatch.setattr(api, "post", post)
    at = app()
    at.selectbox[0].select("sound")
    at.text_area[0].set_value(REPORT["description"])
    at.text_input[0].set_value("Bairro sintético")
    at.number_input[0].set_value(-23.55)
    at.number_input[1].set_value(-46.63)
    at.checkbox[0].check()
    at.checkbox[1].check()
    button(at, "Analisar relato").click().run()
    assert at.error
    button(at, "Analisar relato").click().run()
    assert not at.exception
    assert attempts[0]["client_request_id"] == attempts[1]["client_request_id"]
    button(at, "Novo relato").click().run()
    assert not at.exception
    assert at.text_area[0].value == ""
    assert "report_attempt" not in at.session_state


def test_sequence_empty_form_and_results_render(backend):
    from io import BytesIO
    from PIL import Image
    photo = BytesIO()
    Image.new("RGB", (16, 16), "gray").save(photo, format="PNG")
    at = app()
    at.radio[0].set_value("Sequência de imagens").run()
    button(at, "Analisar sequência").click().run()
    assert at.error and not backend["calls"]
    at.session_state["vision_sequence_results"] = [{"frame": 1, "photo": photo.getvalue(),
        "result": {"mode": "unavailable", "detections": [], "warnings": ["Modelo indisponível"], "latency_ms": 0}},
        {"frame": 2, "photo": photo.getvalue(), "error": "Falha de conexão"}]
    at.run()
    assert not at.exception
    assert len(at.dataframe) == 1
    assert any("Modelo indisponível" in w.value for w in at.warning)
    assert any("Falha de conexão" in e.value for e in at.error)


def test_register_review_protocol_and_manager(backend):
    at = app()
    at.selectbox[0].select("sound")
    at.text_area[0].set_value(REPORT["description"])
    at.text_input[0].set_value("Bairro de teste")
    at.number_input[0].set_value(-23.55)
    at.number_input[1].set_value(-46.63)
    at.checkbox[0].check()
    at.checkbox[1].check()
    button(at, "Analisar relato").click().run()
    assert not at.exception
    assert backend["reports"][0]["status"] == "pending_review"
    assert len(backend["calls"]) == 1
    at.radio[0].set_value("Acompanhar e revisar").run()
    assert not at.exception
    assert at.selectbox[1].options == ["Relato sonoro"]
    assert any("nova ocorrência com foto" in caption.value for caption in at.caption)
    assert not any(b.label == "Criar protocolo interno" for b in at.button)
    button(at, "Salvar minha revisão").click().run()
    assert len(backend["calls"]) == 1
    at.checkbox[0].check()
    button(at, "Salvar minha revisão").click().run()
    assert not at.exception
    assert backend["reports"][0]["status"] == "approved"
    button(at, "Criar protocolo interno").click().run()
    assert not at.exception
    assert backend["reports"][0]["protocol"] == "DEMO-0001"
    at.radio[0].set_value("Painel do gestor").run()
    assert len(at.get("plotly_chart")) == 1
    assert at.selectbox[1].options == ["Em atendimento simulado"]
    button(at, "Salvar situação simulada").click().run()
    assert not at.exception
    assert backend["reports"][0]["status"] == "in_progress"
    assert at.selectbox[1].options == ["Concluído na simulação"]
    button(at, "Salvar situação simulada").click().run()
    assert not at.exception
    assert backend["reports"][0]["status"] == "resolved"


def test_dashboard_controls_change_display(backend):
    backend["reports"] = [copy.deepcopy(REPORT), dict(copy.deepcopy(REPORT), id="second", category="pothole", status="resolved")]
    at = app()
    at.radio[0].set_value("Painel do gestor").run()
    assert len(at.get("plotly_chart")) == 1
    at.multiselect[0].set_value(["sound"]).run()
    assert not at.exception
    assert len(at.dataframe[0].value) == 1
    at.multiselect[1].set_value(["resolved"]).run()
    assert len(at.get("plotly_chart")) == 0
    assert any("Nenhum relato" in message.value for message in at.info)


def test_assistant_preserves_and_sends_history(backend):
    at = app()
    at.radio[0].set_value("Agente do bairro").run()
    at.chat_input[0].set_value("Como revisar meu relato?").run()
    assert not at.exception
    assert len(at.chat_message) == 2
    at.chat_input[0].set_value("E depois da revisão?").run()
    assert not at.exception
    assert len(at.chat_message) == 4
    assert len(backend["calls"][-1][1]["history"]) == 2
    assert backend["calls"][-1][1]["history"][0]["role"] == "user"


def test_api_unavailable_is_user_facing(backend, monkeypatch):
    def fail(*args, **kwargs):
        raise api.APIError("O serviço está indisponível no momento.")
    monkeypatch.setattr(api, "get", fail)
    api.health.clear()
    at = app()
    assert not at.exception
    assert any("Serviço indisponível" in w.value for w in at.warning)
    at.radio[0].set_value("Acompanhar e revisar").run()
    assert not at.exception
    assert "indisponível" in at.error[0].value


def test_invalid_assistant_answer_does_not_enter_history(backend, monkeypatch):
    monkeypatch.setattr(api, "post", lambda *args, **kwargs: {"answer": ""})
    at = app()
    at.radio[0].set_value("Agente do bairro").run()
    at.chat_input[0].set_value("Como fazer o registro?").run()
    assert not at.exception
    assert at.session_state["chat_history"] == []
    assert any("incompleta" in message.value for message in at.error)


def test_integration_view_renders_pending_evidence(backend):
    at = app()
    at.radio[0].set_value("Projeto e transparência").run()
    assert not at.exception
    assert any("Teste móvel" in m.value for m in at.markdown)
    at.radio[0].set_value("Acessibilidade sonora").run()
    assert not at.exception
    assert any("8765/mobile.html" in str(link.proto.url) for link in at.get("link_button"))
    assert any("Nenhum evento sonoro" in c.value for c in at.caption)


@pytest.mark.parametrize("error", [requests.Timeout("SECRET"), requests.ConnectionError("SECRET")])
def test_transport_does_not_expose_error_details(monkeypatch, error):
    def fail(*args, **kwargs):
        raise error
    monkeypatch.setattr(requests, "request", fail)
    with pytest.raises(api.APIError) as captured:
        api.request("GET", "/health")
    assert "SECRET" not in str(captured.value)


def test_bad_json_response_is_handled(monkeypatch):
    class Response:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): raise ValueError("SECRET")
    monkeypatch.setattr(requests, "request", lambda *args, **kwargs: Response())
    with pytest.raises(api.APIError, match="Não foi possível ler"):
        api.request("GET", "/health")


def test_filter_reports_applies_both_controls():
    reports = [REPORT, dict(REPORT, id="two", category="pothole"), dict(REPORT, id="three", status="resolved")]
    assert filter_reports(reports, ["sound"], ["pending_review"]) == [REPORT]


def test_integration_data_tables_and_limits(backend, monkeypatch):
    original_get = api.get
    def get(path):
        if path != "/integrations":
            return original_get(path)
        return [
            {"discipline": "cluster-computing", "data_path": "cluster/resultados.json", "data": {
                "scenarios": [{"workers": 2, "total_simulated_time_s": 180}, {"workers": 4, "total_simulated_time_s": 90}],
                "derived": {"reduction_percent": 50, "ratio_t2_t4": 2}}},
            {"discipline": "computacao-quantica", "data_path": "quantica/resumo.json", "data": {
                "quantum_executed": False, "quantum_advantage_demonstrated": False,
                "vision_benchmark": {"measured_calls": 153, "measured_runs": 27}, "pending": ["Validar carga"]}},
            {"discipline": "nlp-chatbots-virtual-agents", "data_path": "nlp/qualidade.json", "data": {
                "estatisticas": {"texto": {"exemplos": 125}, "qa": {"exemplos": 102}, "chat": {"exemplos": 30}, "teste": {"exemplos": 20}},
                "revisao_humana": {"status": "PENDENTE", "realizada": 0}}},
        ]
    monkeypatch.setattr(api, "get", get)
    at = app()
    at.radio[0].set_value("Projeto e transparência").run()
    assert not at.exception
    assert len(at.dataframe) == 3
    assert at.dataframe[0].value["Nós de processamento"].tolist() == [2, 4]
    assert at.dataframe[2].value["Exemplos"].tolist() == [125, 102, 30, 20]
    assert any("não houve execução quântica" in x.value for x in at.warning)
    assert any("carga sintética" in x.value for x in at.warning)
    assert any("Revisão humana: PENDENTE" in x.value for x in at.caption)


def test_sound_result_becomes_reviewable_report_without_retyping_analysis(backend, monkeypatch):
    import streamlit as st
    from test_sound_recognition import wav, EVENT
    event = copy.deepcopy(EVENT)
    event.update(event_id='yamnet-ui-fixture', label='campainha', confidence=.9)
    monkeypatch.setattr(st, 'audio_input', lambda *a, **kw: wav())
    original_post = api.post
    def post(path, payload=None):
        if path == '/audio/analyze':
            return copy.deepcopy(event)
        result = original_post(path, payload)
        if path == '/reports':
            backend['reports'][-1]['sound_event'] = copy.deepcopy(event)
            result['sound_event'] = copy.deepcopy(event)
        return result
    monkeypatch.setattr(api, 'post', post)
    at = app()
    at.radio[0].set_value('Acessibilidade sonora').run()
    at.checkbox[0].check()
    button(at, 'Analisar áudio').click().run()
    assert not at.exception
    assert any(b.label == 'Criar relato com esta análise' for b in at.button)
    button(at, 'Criar relato com esta análise').click().run()
    assert at.radio[0].value == 'Registrar ocorrência'
    assert at.selectbox[0].value == 'sound'
    assert any('Campainha' in x.value for x in at.markdown)
    at.text_area[0].set_value(REPORT['description'])
    at.text_input[0].set_value('Bairro de teste')
    at.number_input[0].set_value(-23.55)
    at.number_input[1].set_value(-46.63)
    at.checkbox[0].check()
    at.checkbox[1].check()
    button(at, 'Analisar relato').click().run()
    assert at.error and not backend['reports']  # Explicit confirmation of the association.
    at.checkbox[2].check()
    button(at, 'Analisar relato').click().run()
    assert not at.exception
    assert backend['calls'][-1][1]['sound_event_id'] == event['event_id']
    assert 'sound_event' not in backend['calls'][-1][1]
    assert any(b.label == 'Conferir este relato' for b in at.button)
    button(at, 'Conferir este relato').click().run()
    assert next(r for r in at.radio if r.label == 'O que você quer fazer?').value == 'Acompanhar e revisar'
    assert any('Análise sonora vinculada' in x.value for x in at.markdown)
    fresh = app()
    fresh.radio[0].set_value('Acompanhar e revisar').run()
    assert not fresh.exception
    assert any('Campainha' in x.value for x in fresh.markdown)


def test_new_report_discards_previous_audio_link():
    from frontend.state.session import reset_report_form
    state = {'draft_sound_event': {'event_id': 'yamnet-previous'}, 'report_attempt': {'a': 1}}
    reset_report_form(state)
    assert 'draft_sound_event' not in state

def test_sequence_submit_keeps_results_separate_from_form_key(backend, monkeypatch):
    from io import BytesIO
    from frontend.features import vision_sequence
    monkeypatch.setattr(vision_sequence, 'file_picker', lambda *a, **kw: [BytesIO(b'one'), BytesIO(b'two')])
    def unavailable(*args, **kwargs):
        raise api.APIError('Detector indisponível no teste')
    monkeypatch.setattr(api, 'post', unavailable)
    at = app()
    at.radio[0].set_value('Sequência de imagens').run()
    at.checkbox[0].check()
    button(at, 'Analisar sequência').click().run()
    assert not at.exception
    assert len(at.session_state['vision_sequence_results']) == 2
    assert len(at.dataframe) == 1
    at.run()
    assert not at.exception
    assert len(at.session_state['vision_sequence_results']) == 2
