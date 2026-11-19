"""Input/decision tests use explicit artificial fixtures, not measured model accuracy."""
from io import BytesIO
import json
import os
import struct
import subprocess
import wave

import pytest

from backend.providers import audio


def wav_bytes(seconds=1, rate=16000, channels=1, width=2, value=0):
    buffer = BytesIO()
    with wave.open(buffer, 'wb') as wav:
        wav.setnchannels(channels); wav.setsampwidth(width); wav.setframerate(rate)
        sample = struct.pack('<h', value) if width == 2 else b'\0' * width
        wav.writeframes(sample * (round(seconds * rate) * channels))
    return buffer.getvalue()


def fixture_scores(top='Doorbell', score=.8, second=None):
    labels = ['Doorbell', 'Ding-dong', 'Knock', 'Speech', 'Silence'] + [f'fixture-{i}' for i in range(516)]
    scores = [.001] * 521
    scores[labels.index(top)] = score
    if second: scores[labels.index(second[0])] = second[1]
    return {'labels': labels, 'scores': scores, 'model_sha256': audio.MODEL_SHA256,
            'model_version': audio.MODEL_VERSION, 'frame_count': 2,
            'frame_scores': [scores.copy(), scores.copy()]}


def frame_output(frames):
    output = fixture_scores()
    output['frame_count'] = len(frames)
    output['frame_scores'] = frames
    output['scores'] = [sum(frame[i] for frame in frames) / len(frames) for i in range(521)]
    return output


def decoded_summary(raw):
    # Exercise numerical dependencies in their actual isolated runtime, so the
    # application test environment need not install SciPy/TensorFlow itself.
    python = audio._paths()[2]
    if not python.is_file(): pytest.skip('Install isolated audio runtime to run numerical resampling checks.')
    code = """import json,sys
sys.path.insert(0, sys.argv[1])
from backend.providers.audio import _decode_wav
samples, metadata = _decode_wav(sys.stdin.buffer.read())
print(json.dumps({'shape':list(samples.shape),'dtype':samples.dtype.name,
                  'first':float(samples[0]),'middle':float(samples[len(samples)//2]),'metadata':metadata}))
"""
    process = subprocess.run([str(python), '-c', code, str(audio.APP_ROOT)], input=raw,
                             capture_output=True, timeout=30, check=True,
                             creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    return json.loads(process.stdout)


@pytest.mark.parametrize('raw', [b'', b'not a wav', wav_bytes(.99), wav_bytes(15.01),
                                  wav_bytes(rate=7999), wav_bytes(rate=48001),
                                  wav_bytes(channels=3), wav_bytes(width=1),
                                  wav_bytes()[:-3], b'0' * (3 * 1024 * 1024 + 1)],
                         ids=['empty', 'not-wav', 'too-short', 'too-long', 'low-rate',
                              'high-rate', 'three-channels', 'not-pcm16', 'truncated', 'too-large'])
def test_invalid_audio_rejected_before_model_call(monkeypatch, raw):
    def forbidden(_): raise AssertionError('Model must not run for invalid input')
    monkeypatch.setattr(audio, '_run_model', forbidden)
    with pytest.raises(ValueError): audio.analyze_audio(raw)


def test_forged_header_duration_rejected_before_decode(monkeypatch):
    raw = bytearray(wav_bytes())
    raw[40:44] = struct.pack('<I', 16000 * 60 * 60 * 2)
    monkeypatch.setattr(audio, '_run_model', lambda _: pytest.fail('Must reject forged RIFF/data sizes'))
    with pytest.raises(ValueError): audio.analyze_audio(bytes(raw))


@pytest.mark.parametrize('rate,channels', [(8000, 1), (16000, 2), (44100, 2), (48000, 1)])
def test_valid_pcm_normalized_resampled_to_exact_16khz(rate, channels):
    raw = wav_bytes(seconds=1, rate=rate, channels=channels, value=16384)
    summary = decoded_summary(raw)
    metadata = summary['metadata']
    assert summary['shape'] == [16000]
    assert summary['dtype'] == 'float32'
    assert abs(summary['middle'] - .5) < .005
    assert metadata['duration_seconds'] == 1
    assert metadata['source_sample_rate'] == rate


@pytest.mark.parametrize('label,expected', [('Doorbell', 'campainha'), ('Ding-dong', 'campainha'),
                                          ('Knock', 'batida'), ('Speech', 'outro'), ('Silence', 'outro')])
def test_real_vocabulary_mapping_does_not_force_environment(monkeypatch, label, expected):
    monkeypatch.setattr(audio, '_run_model', lambda _: fixture_scores(label))
    result = audio.analyze_audio(wav_bytes())
    assert result['mode'] == 'yamnet'
    assert result['label'] == expected
    assert result['confidence'] == .8
    assert result['sample_rate'] == 16000
    assert result['duration_seconds'] == 1
    assert result['model_sha256'] == audio.MODEL_SHA256
    assert result['top_classes'][0] == {'label': label, 'score': .8}
    assert len(result['top_classes']) == 5
    assert result['latency_ms'] >= 0
    assert any('heur' in warning.lower() for warning in result['warnings'])


def test_low_score_is_uncertain_and_retains_original_top_score(monkeypatch):
    monkeypatch.setattr(audio, '_run_model', lambda _: fixture_scores('Doorbell', .2))
    result = audio.analyze_audio(wav_bytes())
    assert result['label'] == 'incerto'
    assert result['confidence'] == .2
    assert result['top_classes'][0]['score'] == .2


def test_competing_target_classes_are_uncertain(monkeypatch):
    monkeypatch.setattr(audio, '_run_model', lambda _: fixture_scores('Doorbell', .8, ('Knock', .77)))
    assert audio.analyze_audio(wav_bytes())['label'] == 'incerto'


@pytest.mark.parametrize('bad', [float('nan'), float('inf'), -1, 1.1])
def test_invalid_model_output_never_becomes_prediction(monkeypatch, bad):
    output = fixture_scores(); output['scores'][0] = bad
    monkeypatch.setattr(audio, '_run_model', lambda _: output)
    with pytest.raises(audio.AudioUnavailable): audio.analyze_audio(wav_bytes())


def test_missing_model_is_unavailable_not_a_fake_classification(monkeypatch, tmp_path):
    monkeypatch.setenv('YAMNET_MODEL_PATH', str(tmp_path / 'missing.tflite'))
    status = audio.model_status()
    assert status['available'] is False
    assert status['loaded'] is False
    assert status['decision_version'] == 'temporal-v1'
    assert status['reason']
    with pytest.raises(audio.AudioUnavailable): audio.analyze_audio(wav_bytes())


def test_available_status_exposes_policy_without_running_inference(monkeypatch):
    monkeypatch.setattr(audio, '_assets', lambda: (None, None, None))
    monkeypatch.setattr(audio, '_run_model', lambda _: pytest.fail('Status must not infer'))
    status = audio.model_status()
    assert status['available'] is True
    assert status['loaded'] is False
    assert status['decision_version'] == 'temporal-v1'
    assert status['model_version'] == audio.MODEL_VERSION


@pytest.mark.parametrize('field,value', [('model_sha256', 'f' * 64), ('model_version', 'untrusted-version'),
                                        ('model_version', None)])
def test_corrupted_worker_identity_is_unavailable(monkeypatch, field, value):
    output = fixture_scores()
    if value is None: output.pop(field)
    else: output[field] = value
    monkeypatch.setattr(audio, '_run_model', lambda _: output)
    with pytest.raises(audio.AudioUnavailable): audio.analyze_audio(wav_bytes())


def test_stereo_downmix_does_not_overflow():
    data = BytesIO()
    with wave.open(data, 'wb') as wav:
        wav.setparams((2, 2, 16000, 0, 'NONE', 'not compressed'))
        wav.writeframes(struct.pack('<hh', 32767, -32768) * 16000)
    assert abs(decoded_summary(data.getvalue())['first']) < .0001


def test_short_event_detected_even_when_mean_is_silence(monkeypatch):
    silence = fixture_scores('Silence')['scores']
    bell = fixture_scores('Doorbell', .7)['scores']
    output = frame_output([silence, bell, silence, silence, silence, silence])
    monkeypatch.setattr(audio, '_run_model', lambda _: output)
    result = audio.analyze_audio(wav_bytes(seconds=3))
    assert result['label'] == 'campainha'
    assert result['confidence'] == .7
    assert result['decision_version'] == 'temporal-v1'
    assert result['aggregation'] == 'target_event_windows'
    assert result['mean_top_classes'][0]['label'] == 'Silence'
    assert result['top_classes'][0] == {'label': 'Doorbell', 'score': .7}
    assert result['event_windows'] == [{'start_seconds': .48, 'end_seconds': 1.455, 'label': 'campainha', 'score': .7}]


def test_weak_target_never_becomes_temporal_event(monkeypatch):
    monkeypatch.setattr(audio, '_run_model', lambda _: fixture_scores('Doorbell', .34))
    result = audio.analyze_audio(wav_bytes())
    assert result['label'] == 'incerto'
    assert result['event_windows'] == []


def test_stronger_nontarget_in_window_prevents_target_event(monkeypatch):
    silence = fixture_scores('Silence')['scores']
    mixed = fixture_scores('Speech', .9, ('Doorbell', .8))['scores']
    monkeypatch.setattr(audio, '_run_model', lambda _: frame_output([silence, mixed, silence, silence, silence, silence]))
    result = audio.analyze_audio(wav_bytes(seconds=3))
    assert result['label'] == 'outro'
    assert result['event_windows'] == []


def test_competing_events_in_different_windows_are_uncertain(monkeypatch):
    silence = fixture_scores('Silence')['scores']
    bell = fixture_scores('Doorbell', .8)['scores']
    knock = fixture_scores('Knock', .77)['scores']
    monkeypatch.setattr(audio, '_run_model', lambda _: frame_output([silence, bell, knock, silence, silence, silence]))
    result = audio.analyze_audio(wav_bytes(seconds=3))
    assert result['label'] == 'incerto'
    assert len(result['event_windows']) == 2
    assert result['top_classes'][0] == {'label': 'Doorbell', 'score': .8}


def test_event_end_clamped_to_real_duration(monkeypatch):
    silence = fixture_scores('Silence')['scores']
    bell = fixture_scores('Doorbell', .7)['scores']
    monkeypatch.setattr(audio, '_run_model', lambda _: frame_output([silence, silence, silence, silence, silence, bell]))
    result = audio.analyze_audio(wav_bytes(seconds=3))
    assert result['event_windows'] == [{'start_seconds': 2.4, 'end_seconds': 3.0, 'label': 'campainha', 'score': .7}]


@pytest.mark.parametrize('kind', ['missing', 'not-list', 'empty', 'too-many', 'wrong-classes',
                                  'nan', 'negative', 'too-high', 'wrong-count', 'mean-diverges'])
def test_malformed_frames_are_unavailable(monkeypatch, kind):
    output = fixture_scores()
    if kind == 'missing': output.pop('frame_scores')
    elif kind == 'not-list': output['frame_scores'] = 'not frames'
    elif kind == 'empty': output['frame_scores'] = []
    elif kind == 'too-many': output['frame_scores'] *= 16
    elif kind == 'wrong-classes': output['frame_scores'][0] = [0.0]
    elif kind == 'nan': output['frame_scores'][0][0] = float('nan')
    elif kind == 'negative': output['frame_scores'][0][0] = -.1
    elif kind == 'too-high': output['frame_scores'][0][0] = 1.1
    elif kind == 'wrong-count': output['frame_count'] = 1
    elif kind == 'mean-diverges': output['scores'][0] = .1
    monkeypatch.setattr(audio, '_run_model', lambda _: output)
    with pytest.raises(audio.AudioUnavailable): audio.analyze_audio(wav_bytes())
