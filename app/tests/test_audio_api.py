"""Audio route/storage behavior; model scores are fixtures, not acoustic validation."""
import base64
from concurrent.futures import ThreadPoolExecutor
import sys
import types
import pytest
from fastapi.testclient import TestClient


class FixtureUnavailable(RuntimeError):
    pass


@pytest.fixture
def audio_api(tmp_path, monkeypatch):
    monkeypatch.setenv('DB_PATH', str(tmp_path / 'audio.sqlite3'))
    import backend.providers
    calls = []
    def analyze(raw):
        calls.append(raw)
        return dict(mode='yamnet', model_version='fixture-not-real-yamnet', model_sha256='f'*64,
                    label='batida', confidence=.8, top_classes=[{'label':'Knock','score':.8}],
                    duration_seconds=5.0, sample_rate=16000, latency_ms=10.0, warnings=[])
    provider = types.SimpleNamespace(analyze_audio=analyze, AudioUnavailable=FixtureUnavailable,
                                     model_status=lambda: {'available':True, 'model_version':'fixture'})
    monkeypatch.setitem(sys.modules, 'backend.providers.audio', provider)
    monkeypatch.setattr(backend.providers, 'audio', provider, raising=False)
    from backend.main import app
    with TestClient(app) as client:
        yield client, provider, calls


def payload(raw=b'provider-fixture'):
    return {'client_request_id':'audio-retry-01', 'audio_base64':base64.b64encode(raw).decode()}


def test_analysis_persists_server_origin_without_audio_and_retry_skips_inference(audio_api):
    client, _, calls = audio_api
    response = client.post('/audio/analyze', json=payload())
    assert response.status_code == 201, response.text
    event = response.json()
    assert event['source'] == 'yamnet' and event['label'] == 'batida'
    assert event['event_id'] == 'yamnet-audio-retry-01'
    assert 'audio_base64' not in str(client.get('/sound-events').json())
    assert client.get('/sound-events').json() == [event]
    assert client.post('/audio/analyze', json=payload()).json() == event
    assert len(calls) == 1  # Retry must not run an expensive model again.
    assert client.post('/audio/analyze', json=payload(b'changed')).status_code == 409
    assert len(client.get('/sound-events').json()) == 1


def test_concurrent_analysis_creates_one_event(audio_api):
    client, _, _ = audio_api
    with ThreadPoolExecutor(max_workers=3) as pool:
        responses = list(pool.map(lambda _: client.post('/audio/analyze', json=payload()), range(3)))
    assert all(r.status_code == 201 for r in responses)
    assert responses[0].json() == responses[1].json() == responses[2].json()
    assert len(client.get('/sound-events').json()) == 1


def test_bad_audio_and_unavailable_model_do_not_persist(audio_api):
    client, provider, _ = audio_api
    assert client.post('/audio/analyze', json={**payload(), 'audio_base64':'!bad'}).status_code == 422
    assert client.post('/audio/analyze', json=payload(b'')).status_code == 422
    assert client.post('/audio/analyze', json=payload(b'x'*3_000_001)).status_code == 422
    def unavailable(raw):
        raise FixtureUnavailable('Modelo não instalado')
    provider.analyze_audio = unavailable
    assert client.post('/audio/analyze', json=payload()).status_code == 503
    assert client.get('/sound-events').json() == []
    def invalid(raw):
        raise ValueError('WAV inválido')
    provider.analyze_audio = invalid
    assert client.post('/audio/analyze', json=payload()).status_code == 422
    assert client.get('/sound-events').json() == []


def test_manual_ingestion_cannot_claim_yamnet_provenance(audio_api):
    client, _, _ = audio_api
    event = dict(event_id='yamnet-forged', source='manual', label='batida', confidence=.9,
                 model_version='fixture', observed_at='2026-11-11T00:00:00-03:00')
    assert client.post('/sound-events', json=event).status_code == 409
    assert client.post('/sound-events', json={**event,'event_id':'test','source':'yamnet'}).status_code == 422
    assert client.post('/audio/analyze', json={**payload(),'label':'campainha'}).status_code == 422
    assert client.get('/sound-events').json() == []


def test_audio_status_reports_capability_without_inference(audio_api):
    client, _, calls = audio_api
    response = client.get('/audio/status')
    assert response.status_code == 200
    assert response.json()['available'] is True
    assert calls == []


def sound_report(event_id=None):
    data = dict(client_request_id='linked-report-01', description='Relato sonoro público para demonstração.',
                neighborhood='Bairro de demonstração', latitude=-23.55, longitude=-46.63,
                location_confirmed=True, category='sound')
    if event_id is not None:
        data['sound_event_id'] = event_id
    return data


def test_audio_follows_report_through_review_retry_and_new_session(audio_api, monkeypatch):
    client, _, calls = audio_api
    monkeypatch.setenv('LLM_MODE', 'extractive')
    event = client.post('/audio/analyze', json=payload()).json()
    data = sound_report(event['event_id'])
    response = client.post('/reports', json=data)
    assert response.status_code == 201, response.text
    report = response.json()
    assert report['sound_event'] == event  # Canonical stored analysis, not client supplied scores.
    assert report['analysis']['mode'] == 'yamnet'
    assert report['analysis']['confidence'] == event['confidence']
    assert report['status'] == 'pending_review' and report['protocol'] is None
    assert client.post(f"/reports/{report['id']}/protocol").status_code == 409
    assert client.post('/reports', json=data).json()['id'] == report['id']
    assert len(client.get('/reports').json()) == 1 and len(calls) == 1
    assert client.post(f"/reports/{report['id']}/review", json={
        'approved': True, 'corrected_category': 'sound'}).status_code == 200
    protocol = client.post(f"/reports/{report['id']}/protocol").json()
    assert protocol['protocol'].startswith('SIM-') and protocol['sound_event'] == event
    from backend.main import app
    with TestClient(app) as fresh:
        recovered = fresh.get(f"/reports/{report['id']}").json()
    assert recovered['sound_event'] == event and 'audio_base64' not in str(recovered)


def test_report_rejects_missing_manual_and_mismatched_audio_links(audio_api, monkeypatch):
    client, _, _ = audio_api
    monkeypatch.setenv('LLM_MODE', 'extractive')
    assert client.post('/reports', json=sound_report('missing')).status_code == 422
    manual = dict(event_id='manual-01', source='manual', label='batida', confidence=.9,
                  model_version='declared', observed_at='2026-11-18T00:00:00Z')
    assert client.post('/sound-events', json=manual).status_code == 201
    response = client.post('/reports', json=sound_report('manual-01'))
    assert response.status_code == 422 and 'YAMNet' in response.text
    event = client.post('/audio/analyze', json=payload()).json()
    response = client.post('/reports', json={**sound_report(event['event_id']), 'category': 'pothole'})
    assert response.status_code == 422 and 'sonor' in response.text
    assert client.post('/reports', json={**sound_report(event['event_id']),
        'sound_event': {**event, 'confidence': 1}}).status_code == 422
    assert client.get('/reports').json() == []


def test_neighborhood_classification_preserved_in_review_and_protocol(audio_api, monkeypatch):
    client, provider, _ = audio_api
    monkeypatch.setenv('LLM_MODE', 'extractive')
    original = provider.analyze_audio
    source = dict(label='furadeira', score=.82, model_class='Drill',
                  version='neighborhood-v1', aggregation='clip_mean')
    provider.analyze_audio = lambda raw: {**original(raw), 'neighborhood_source': source}
    event = client.post('/audio/analyze', json=payload()).json()
    report = client.post('/reports', json=sound_report(event['event_id'])).json()
    assert 'furadeira' in report['analysis']['summary'].lower()
    assert report['analysis']['confidence'] == .82
    assert report['sound_event']['analysis']['neighborhood_source'] == source
    assert client.post(f"/reports/{report['id']}/protocol").status_code == 409
    client.post(f"/reports/{report['id']}/review", json={'approved': True, 'corrected_category': 'sound'})
    final = client.post(f"/reports/{report['id']}/protocol").json()
    assert final['sound_event']['analysis']['neighborhood_source'] == source
