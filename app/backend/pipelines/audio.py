"""Server-generated YAMNet events. Raw audio never enters persistent storage."""
import base64
import binascii
import hashlib
from backend.providers import storage
from backend.schemas import AudioInput


def analyze(data: AudioInput):
    from backend.providers import audio
    try:
        raw = base64.b64decode(data.audio_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError('O áudio deve ser um WAV válido em base64.') from exc
    if not raw or len(raw) > 3_000_000:
        raise ValueError('Envie um WAV com até 3 MB.')
    digest = hashlib.sha256(raw).hexdigest()
    event_id = 'yamnet-' + data.client_request_id
    existing = storage.existing_audio_event(event_id, digest)
    if existing:
        return existing
    analysis = audio.analyze_audio(raw)
    event = {'event_id':event_id, 'source':'yamnet', 'label':analysis['label'],
             'confidence':analysis['confidence'], 'model_version':analysis['model_version'],
             'observed_at':storage.now(), 'audio_sha256':digest, 'analysis':analysis}
    return storage.save_audio_event(event)
