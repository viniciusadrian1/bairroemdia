import base64
import binascii
import uuid
import hashlib
import json
from io import BytesIO
from PIL import Image, ImageOps, UnidentifiedImageError
from backend.providers import storage
from backend.schemas import ReportInput, ReviewInput
from .assistant import answer
from .privacy import mask


def image_bytes(encoded):
    try:
        raw=base64.b64decode(encoded,validate=True)
        if not raw or len(raw)>5_000_000:
            raise ValueError('A foto deve ter até 5 MB.')
        with Image.open(BytesIO(raw)) as im:
            if im.width*im.height>20_000_000 or im.format not in ('JPEG','PNG','WEBP'):
                raise ValueError('Use JPG, PNG ou WebP com até 20 megapixels.')
            im.verify()
        return raw
    except (binascii.Error, UnidentifiedImageError, OSError, Image.DecompressionBombError) as e:
        raise ValueError('A foto não é uma imagem válida.') from e


def sanitized_photo(encoded):
    raw = image_bytes(encoded)
    with Image.open(BytesIO(raw)) as original:
        oriented = ImageOps.exif_transpose(original).convert('RGB')
        oriented.thumbnail((2560, 2560), Image.Resampling.LANCZOS)
        # A fresh image has neither EXIF/GPS nor inherited ICC/comments.
        clean = Image.new('RGB', oriented.size)
        clean.paste(oriented)
        out = BytesIO()
        clean.save(out, format='JPEG', quality=90)
    if len(out.getvalue()) > 5_000_000:
        raise ValueError('A foto saneada excede 5 MB. Reduza sua resolução.')
    return out.getvalue()


def create(data:ReportInput):
    fingerprint_data = data.model_dump(exclude={'client_request_id'})
    if data.sound_event_id is None:
        fingerprint_data.pop('sound_event_id')  # Preserve retry identity of clients predating audio links.
    fingerprint = hashlib.sha256(json.dumps(fingerprint_data,
        sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
    existing = storage.existing_request(data.client_request_id, fingerprint)
    if existing:
        return existing
    sound_event = None
    if data.sound_event_id:
        if data.category != 'sound':
            raise ValueError('Uma análise sonora só pode ser vinculada a um relato sonoro.')
        sound_event = storage.analyzed_sound_event(data.sound_event_id)
    vision=None
    raw=None
    if data.image_base64:
        raw=sanitized_photo(data.image_base64)
        try:
            from backend.providers.vision import analyze_image
            vision=analyze_image(raw)
        except ImportError:
            vision={'mode':'unavailable','detections':[],'warnings':['Detector não disponível.']}
    if data.category=='pothole' and not data.image_base64:
        raise ValueError('Inclua uma foto do dano na pavimentação.')
    description=mask(data.description)
    warnings=['Triagem educacional; a revisão humana é obrigatória.']
    confidence=None
    mode='rules'
    if vision:
        warnings+=vision.get('warnings',[])
        detections=vision.get('detections',[])
        if detections:
            confidence=max(d['confidence'] for d in detections)
            mode=vision['mode']
    summary=('Relato de possível dano na pavimentação. Confirmar pela imagem e inspeção.'
             if data.category=='pothole' else 'Relato sonoro. Não comprova excesso de volume ou infração.')
    if sound_event:
        labels = {'campainha': 'campainha', 'batida': 'batida', 'outro': 'outro som', 'incerto': 'incerto'}
        summary = ('Análise sonora vinculada: ' + labels.get(sound_event['label'], sound_event['label'])
                   + '. Confira se o resultado corresponde ao contexto relatado. Não mede decibéis nem comprova infração.')
        confidence = sound_event['confidence']
        source = (sound_event.get('analysis') or {}).get('neighborhood_source') or {}
        source_labels = {'furadeira': 'furadeira', 'obra_ferramentas': 'obra / ferramentas', 'musica': 'música'}
        if source.get('label') in source_labels:
            summary = ('Tipo de som sugerido: ' + source_labels[source['label']]
                       + '. Confira a análise e descreva o incômodo, o horário e o contexto. Não mede decibéis nem comprova infração.')
            confidence = source['score']
        mode = 'yamnet'
    if not confidence and data.category=='pothole':
        warnings.append('Nenhum dano confirmado automaticamente; categoria informada pelo cidadão.')
    guidance=answer('Como solicitar tapa buraco?' if data.category=='pothole' else 'O que uma classificação sonora comprova?',[])
    return storage.insert({'id':str(uuid.uuid4()),'client_request_id':data.client_request_id,
        'description':description,'neighborhood':mask(data.neighborhood),
        'latitude':data.latitude,'longitude':data.longitude,'location_confirmed':True,'category':data.category,
        'status':'pending_review','created_at':storage.now(),
        'analysis':{'summary':summary,'suggested_category':data.category,'confidence':confidence,'mode':mode,'warnings':warnings},
        'vision':vision,'sound_event_id':data.sound_event_id,'sound_event':sound_event,
        'guidance':guidance,'review':None,'protocol':None}, photo=raw, fingerprint=fingerprint)


def review(report_id,data:ReviewInput):
    def change(r):
        if r['status'] not in ('pending_review','approved','rejected'):
            raise ValueError('O protocolo já foi emitido. A revisão não pode ser alterada nesta etapa.')
        if data.approved and data.corrected_category=='pothole' and not r.get('image_available'):
            raise ValueError('Para pavimentação, registre uma nova ocorrência com foto.')
        r['review']={**data.model_dump(),'note':mask(data.note),'at':storage.now()}
        r['category']=data.corrected_category
        r['status']='approved' if data.approved else 'rejected'
        return r
    return storage.mutate(report_id,change,'review')


def protocol(report_id):
    def change(r):
        if r['protocol']:
            return r
        if r['status']!='approved' or not r.get('review',{}).get('approved'):
            raise ValueError('Revise e aprove a ocorrência antes de emitir um protocolo interno.')
        r['protocol']='SIM-'+r['id'].upper()
        r['status']='protocolled'
        return r
    return storage.mutate(report_id,change,'protocol')


def change_status(report_id,status):
    def change(r):
        allowed={'protocolled':{'in_progress'},'in_progress':{'resolved'},'resolved':set()}
        if status==r['status']: return r
        if status not in allowed.get(r['status'],set()):
            raise ValueError('Avance de protocolado para em atendimento e depois para resolvido.')
        r['status']=status
        return r
    return storage.mutate(report_id,change,'status')
