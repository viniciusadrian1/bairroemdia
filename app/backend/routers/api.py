import os
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from backend.schemas import ReportInput, ReviewInput, StatusInput, AssistantInput, AssistantResponse, SoundEvent, ImageInput, AudioInput
from backend.providers import storage
from backend.pipelines import reports, assistant

router=APIRouter()
ROOT=Path(__file__).resolve().parents[2]


def domain(action, *args, bad=409):
    try:
        return action(*args)
    except KeyError:
        raise HTTPException(404,'Ocorrência não encontrada.')
    except storage.IdempotencyConflict as e:
        raise HTTPException(409,str(e))
    except ValueError as e:
        raise HTTPException(bad,str(e))


@router.get('/health')
def health():
    return {'status':'ok','llm_mode':os.getenv('LLM_MODE','extractive'),
            'vision_mode':'configured' if os.getenv('VISION_MODEL_PATH') else 'unavailable'}


@router.post('/reports',status_code=201)
def create_report(data:ReportInput):
    return domain(reports.create,data,bad=422)


@router.get('/reports')
def list_reports():
    return storage.all_reports()


@router.get('/reports/{report_id}')
def get_report(report_id:str):
    return domain(storage.get,report_id)


@router.post('/reports/{report_id}/review')
def review_report(report_id:str,data:ReviewInput):
    return domain(reports.review,report_id,data)


@router.get('/reports/{report_id}/image')
def get_report_image(report_id:str):
    photo = domain(storage.get_photo,report_id)
    return Response(photo['data'], media_type=photo['mime'], headers={'Cache-Control': 'no-store',
                    'X-Image-SHA256': photo['sha256']})


@router.post('/reports/{report_id}/protocol')
def emit_protocol(report_id:str):
    return domain(reports.protocol,report_id)


@router.post('/reports/{report_id}/status')
def update_status(report_id:str,data:StatusInput):
    return domain(reports.change_status,report_id,data.status)


@router.post('/assistant',response_model=AssistantResponse)
def ask(data:AssistantInput):
    return assistant.answer(data.question,[m.model_dump() for m in data.history])


@router.post('/vision')
def vision(data:ImageInput):
    from backend.providers.vision import analyze_image
    return domain(lambda:analyze_image(reports.image_bytes(data.image_base64)),bad=422)


@router.post('/sound-events',status_code=201)
def sound_event(data:SoundEvent):
    if data.event_id.startswith('yamnet-'):
        raise HTTPException(409,'Identificador reservado às análises executadas pelo servidor.')
    return domain(storage.sound_event,data.model_dump(mode='json'))


@router.get('/sound-events')
def sound_events():
    return storage.sound_events()


@router.get('/audio/status')
def audio_status():
    from backend.providers.audio import model_status
    return model_status()


@router.post('/audio/analyze', status_code=201)
def analyze_audio(data:AudioInput):
    from backend.providers.audio import AudioUnavailable
    from backend.pipelines.audio import analyze
    try:
        return domain(analyze,data,bad=422)
    except AudioUnavailable as exc:
        raise HTTPException(503,str(exc))


@router.get('/integrations')
def integrations():
    """Describe runtime modules without depending on academic delivery folders."""
    return json.loads((ROOT/'resources/integrations.json').read_text(encoding='utf-8'))
