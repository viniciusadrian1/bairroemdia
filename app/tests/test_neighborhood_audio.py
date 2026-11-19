"""Decision contracts using fabricated scores; these do not measure model quality."""
import csv

import pytest

from backend.providers import audio
from test_audio_provider import wav_bytes


def output_with(values):
    with (audio.MODEL_DIR / 'yamnet_class_map.csv').open(encoding='utf-8') as file:
        labels = [row['display_name'] for row in csv.DictReader(file)]
    scores = [values.get(label, .001) for label in labels]
    return {'labels': labels, 'scores': scores, 'frame_scores': [scores[:], scores[:]],
            'frame_count': 2, 'model_version': audio.MODEL_VERSION, 'model_sha256': audio.MODEL_SHA256}


@pytest.mark.parametrize('scores,expected', [
    ({'Drill': .82, 'Power tool': .8}, 'furadeira'),
    ({'Jackhammer': .8, 'Power tool': .79}, 'obra_ferramentas'),
    ({'Sawing': .8}, 'obra_ferramentas'),
    ({'Music': .9}, 'musica'),
    ({'Music': .2}, 'incerto'),
    ({'Music': .8, 'Drill': .78}, 'incerto'),
    ({'Music': .4, 'Speech': .9}, 'outro'),
    ({'Music': .8, 'Speech': .78}, 'incerto'),
    ({'Dog': .9}, 'outro'),
])
def test_source_identifies_supported_family_or_abstains(monkeypatch, scores, expected):
    monkeypatch.setattr(audio, '_run_model', lambda _: output_with(scores))
    result = audio.analyze_audio(wav_bytes())
    source = result['neighborhood_source']
    assert source['label'] == expected
    assert source['aggregation'] == 'clip_mean'
    assert source['score'] == max(scores.values())
    assert source['version']
    assert 'decibels' not in source and 'infraction' not in source


def test_accessibility_event_and_dominant_source_are_independent(monkeypatch):
    output = output_with({'Music': .8})
    # A brief bell must not erase the musical context of the full recording.
    output['frame_scores'][1][output['labels'].index('Doorbell')] = .95
    output['scores'] = [(a + b) / 2 for a, b in zip(*output['frame_scores'])]
    monkeypatch.setattr(audio, '_run_model', lambda _: output)
    result = audio.analyze_audio(wav_bytes())
    assert result['label'] == 'campainha'
    assert result['neighborhood_source']['label'] == 'musica'
    assert result['neighborhood_source']['score'] == .8


def test_status_versions_source_policy_for_request_identity(monkeypatch):
    monkeypatch.setattr(audio, '_assets', lambda: (None, None, None))
    assert audio.model_status()['source_profile_version']
