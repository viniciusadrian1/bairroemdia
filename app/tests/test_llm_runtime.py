"""Explicit local CPU selection must reach Ollama, without changing default policy."""
import httpx
import pytest
from backend.providers import llm


@pytest.mark.parametrize('configured,expected', [('0', 0), (None, None)])
def test_optional_cpu_setting_reaches_ollama(monkeypatch, configured, expected):
    if configured is None:
        monkeypatch.delenv('OLLAMA_NUM_GPU', raising=False)
    else:
        monkeypatch.setenv('OLLAMA_NUM_GPU', configured)
    seen = []
    def respond(request):
        import json
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={'message': {'content': json.dumps({
            'answer': 'Sem evidência.', 'source_ids': [], 'evidence_quotes': [], 'abstained': True})}})
    client_class = httpx.Client
    monkeypatch.setattr(llm.httpx, 'Client', lambda **kw: client_class(transport=httpx.MockTransport(respond)))
    result = llm.generate('Como registrar?', [], [])
    assert result.abstained
    assert seen[0]['options'].get('num_gpu') == expected
