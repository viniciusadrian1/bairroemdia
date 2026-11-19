"""Real local YAMNet evaluation of the frozen three-file selection; retain every result."""
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from uuid import uuid4

import requests

ROOT = Path(__file__).resolve().parent
API = 'http://127.0.0.1:8000'


def main():
    manifest = json.loads((ROOT / 'manifest.json').read_text(encoding='utf-8'))
    evidence = {'executed_at': datetime.now(timezone.utc).isoformat(),
                'scope': 'Exploratory public audio examples; not general accuracy, not physical microphone.',
                'status': requests.get(API + '/audio/status', timeout=10).json(), 'results': []}
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    destination = ROOT / f'results-{stamp}.json'
    for sample in manifest['files']:
        raw = (ROOT / sample['path']).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == sample['wav_sha256']
        payload = {'client_request_id': 'neighborhood-' + uuid4().hex,
                   'audio_base64': base64.b64encode(raw).decode()}
        response = requests.post(API + '/audio/analyze', json=payload, timeout=60)
        response.raise_for_status()
        event = response.json()
        assert event['source'] == 'yamnet' and event['audio_sha256'] == sample['wav_sha256']
        assert requests.post(API + '/audio/analyze', json=payload, timeout=60).json() == event
        actual = event['analysis']['neighborhood_source']
        row = {'sample': sample, 'prediction_matches_reference': actual['label'] == sample['expected'],
               'event': event}
        evidence['results'].append(row)
        destination.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'id': sample['id'], 'expected': sample['expected'], 'actual': actual,
                          'match': row['prediction_matches_reference']}, ensure_ascii=False), flush=True)
    events = requests.get(API + '/sound-events', timeout=10).json()
    for row in evidence['results']:
        assert [e for e in events if e['event_id'] == row['event']['event_id']] == [row['event']]
        assert 'audio_base64' not in json.dumps(row['event'])
    evidence['contract_checks'] = 'Real inference, identities, retry and canonical persistence passed for all samples.'
    destination.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Evidence: ' + str(destination))


if __name__ == '__main__':
    main()
