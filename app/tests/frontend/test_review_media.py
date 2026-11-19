import copy
import io
import sys
from pathlib import Path
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from frontend.providers import api
from frontend.state.session import request_id_for, reset_report_form


def test_retry_id_stable_until_payload_or_explicit_new_report():
    state = {}
    payload = {'description':'Relato sintético', 'category':'sound'}
    first = request_id_for(payload, state)
    assert request_id_for(copy.deepcopy(payload), state) == first
    changed = request_id_for(dict(payload, description='Outro relato sintético'), state)
    assert changed != first
    reset_report_form(state)
    assert request_id_for(payload, state) not in (first, changed)
    assert state['report_form_version'] == 1


def test_binary_image_transport_validates_type_and_bytes(monkeypatch):
    out = io.BytesIO(); Image.new('RGB',(16,16),'gray').save(out,format='PNG')
    class Response:
        status_code = 200
        headers = {'Content-Type':'image/png'}
        content = out.getvalue()
        def raise_for_status(self): pass
    monkeypatch.setattr(api.requests, 'request', lambda *a, **kw: Response())
    assert api.get_image('report-1') == out.getvalue()
    Response.headers = {'Content-Type':'text/html'}
    with pytest.raises(api.APIError, match='imagem'):
        api.get_image('report-1')


def test_binary_image_transport_does_not_expose_server_error(monkeypatch):
    class Response:
        status_code = 500
        headers = {'Content-Type':'text/html'}
        content = b'SECRET'
    monkeypatch.setattr(api.requests, 'request', lambda *a, **kw: Response())
    with pytest.raises(api.APIError) as result:
        api.get_image('report-1')
    assert 'SECRET' not in str(result.value)


def test_sequence_calls_real_contract_and_keeps_per_frame_error(monkeypatch):
    from frontend.features.vision_sequence import analyze_sequence
    files = [io.BytesIO(b'first'), io.BytesIO(b'second')]
    calls = []
    def post(path, payload):
        calls.append((path, payload))
        if len(calls) == 2:
            raise api.APIError('Conexão indisponível')
        return {'mode':'unavailable', 'detections':[], 'warnings':['Sem modelo'], 'latency_ms':0}
    monkeypatch.setattr(api, 'post', post)
    results = analyze_sequence(files)
    assert [path for path, _ in calls] == ['/vision', '/vision']
    assert all(set(payload) == {'image_base64'} for _, payload in calls)
    assert results[0]['result']['mode'] == 'unavailable'
    assert results[1]['error'] == 'Conexão indisponível'
