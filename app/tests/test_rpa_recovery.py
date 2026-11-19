import importlib.util
from pathlib import Path
import requests
from fastapi.testclient import TestClient


def test_rpa_recovers_response_lost_after_server_commit(tmp_path, monkeypatch):
    monkeypatch.setenv('DB_PATH', str(tmp_path / 'rpa.sqlite3'))
    monkeypatch.setenv('LLM_MODE', 'extractive')
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location('rpa_recovery', root / 'automation/robot.py')
    robot = importlib.util.module_from_spec(spec); spec.loader.exec_module(robot)
    from backend.main import app
    lost = False
    with TestClient(app) as client:
        def request(method, url, json=None, **kwargs):
            nonlocal lost
            response = client.request(method, url.replace('http://local', ''), json=json)
            if method == 'POST' and not lost:
                assert response.status_code == 201
                lost = True
                raise requests.Timeout('Synthetic lost response after commit')
            return response
        monkeypatch.setattr(robot.requests, 'request', request)
        csv = tmp_path / 'input.csv'
        csv.write_text('job_id,description,neighborhood,category,latitude,longitude,location_confirmed\n'
                       '1,Relato sonoro sintético,Bairro sintético,sound,-23.55,-46.63,true\n', encoding='utf-8')
        args = ('http://local', csv, tmp_path/'log.jsonl', tmp_path/'checkpoint.json')
        assert robot.run(*args)[0]['outcome'] == 'failed'
        assert len(client.get('/reports').json()) == 1
        assert robot.run(*args)[0]['outcome'] == 'pending_review'
        assert len(client.get('/reports').json()) == 1
        assert robot.run(*args)[0]['outcome'] == 'skipped'
