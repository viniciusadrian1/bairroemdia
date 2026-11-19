"""Validated pavement detector. No model means no invented detections.

ONNX input is a YOLOv8 detection export, default one-class pothole model.
For multi-class RDD exports set VISION_LABELS=D00,D10,D20,D40.
"""
from functools import lru_cache
from io import BytesIO
import logging
import math
import os
from pathlib import Path
from threading import Lock
from time import perf_counter
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError

LOGGER = logging.getLogger(__name__)
MODEL_LOCK = Lock()
MAX_BYTES = 8 * 1024 * 1024
MAX_PIXELS = 20_000_000
LABEL_MAP = {'D00': 'fissura longitudinal', 'D10': 'fissura transversal',
             'D20': 'fissura em malha', 'D40': 'buraco', 'pothole': 'buraco'}


@lru_cache(maxsize=2)
def _load_onnx(path: str, modified: int):
    import cv2
    return cv2.dnn.readNetFromONNX(path)


def _decode_image(data: bytes):
    if not data or len(data) > MAX_BYTES:
        raise ValueError('Envie uma imagem de até 8 MB.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as original:
                if original.format not in {'JPEG', 'PNG', 'WEBP'}:
                    raise ValueError('Use imagem JPEG, PNG ou WEBP.')
                if original.width * original.height > MAX_PIXELS:
                    raise ValueError('A imagem ultrapassa 20 milhões de pixels.')
                original.load()
                return ImageOps.exif_transpose(original).convert('RGB')
    except (UnidentifiedImageError, OSError, Image.DecompressionBombWarning,
            Image.DecompressionBombError) as exc:
        raise ValueError('Não foi possível ler a imagem. Envie uma foto válida.') from exc


def _infer_onnx(image, model_path: Path):
    import cv2
    import numpy as np
    size = int(os.getenv('VISION_IMAGE_SIZE', '640'))
    threshold = float(os.getenv('VISION_CONFIDENCE', '0.25'))
    if not 64 <= size <= 2048 or not 0 < threshold <= 1:
        raise ValueError('Configuração de visão inválida.')
    labels = [x.strip() for x in os.getenv('VISION_LABELS', 'pothole').split(',')]
    if not labels or any(x not in LABEL_MAP for x in labels):
        raise ValueError('O modelo precisa de classes de pavimentação documentadas.')
    width, height = image.size
    ratio = min(size / width, size / height)
    resized_width, resized_height = round(width * ratio), round(height * ratio)
    left, top = (size - resized_width) // 2, (size - resized_height) // 2
    canvas = np.full((size, size, 3), 114, dtype=np.uint8)
    canvas[top:top + resized_height, left:left + resized_width] = cv2.resize(
        np.asarray(image), (resized_width, resized_height))
    blob = cv2.dnn.blobFromImage(canvas, 1 / 255.0, (size, size), swapRB=False)
    with MODEL_LOCK:
        net = _load_onnx(str(model_path), model_path.stat().st_mtime_ns)
        net.setInput(blob)
        raw = net.forward()
    predictions = np.asarray(raw).squeeze()
    if predictions.ndim != 2:
        raise ValueError('Saída ONNX incompatível com detector YOLOv8.')
    if predictions.shape[0] == 4 + len(labels):
        predictions = predictions.T
    if predictions.shape[1] != 4 + len(labels):
        raise ValueError('Classes do modelo não correspondem a VISION_LABELS.')
    boxes, scores, class_ids = [], [], []
    for row in predictions:
        class_id = int(np.argmax(row[4:]))
        score = float(row[4 + class_id])
        if not math.isfinite(score) or score < threshold or score > 1:
            continue
        cx, cy, bw, bh = [float(v) for v in row[:4]]
        if not all(math.isfinite(v) for v in (cx, cy, bw, bh)):
            continue
        x1 = max(0.0, min(width, (cx - bw / 2 - left) / ratio))
        y1 = max(0.0, min(height, (cy - bh / 2 - top) / ratio))
        x2 = max(0.0, min(width, (cx + bw / 2 - left) / ratio))
        y2 = max(0.0, min(height, (cy + bh / 2 - top) / ratio))
        if x2 <= x1 or y2 <= y1:
            continue
        boxes.append([x1, y1, x2 - x1, y2 - y1])
        scores.append(score)
        class_ids.append(class_id)
    kept = []
    for class_id in sorted(set(class_ids)):
        indices = [i for i, c in enumerate(class_ids) if c == class_id]
        picked = cv2.dnn.NMSBoxes([boxes[i] for i in indices],
                                  [scores[i] for i in indices], threshold, 0.45)
        kept.extend(indices[int(i)] for i in np.asarray(picked).reshape(-1))
    detections = []
    for i in sorted(kept, key=lambda x: scores[x], reverse=True):
        x, y, w, h = boxes[i]
        detections.append({'label': LABEL_MAP[labels[class_ids[i]]],
                           'confidence': round(scores[i], 6),
                           'bbox': [round(v, 2) for v in (x, y, x + w, y + h)]})
    return detections


def analyze_image(image_bytes: bytes) -> dict:
    started = perf_counter()
    image = _decode_image(image_bytes)
    result = {'mode': 'unavailable', 'detections': [], 'width': image.width,
              'height': image.height, 'latency_ms': 0.0, 'warnings': []}
    configured = os.getenv('VISION_MODEL_PATH', '').strip()
    if not configured:
        result['warnings'].append('Detector não configurado. A foto exige revisão humana; nenhuma inferência foi realizada.')
    else:
        path = Path(configured)
        if not path.is_file() or path.suffix.lower() != '.onnx':
            result['warnings'].append('Pesos ONNX de pavimentação indisponíveis. Nenhuma inferência foi realizada.')
        else:
            try:
                result['detections'] = _infer_onnx(image, path)
                result['mode'] = 'model'
                result['warnings'].append('Triagem visual: confiança não comprova dano ou gravidade. Confirme a localização e revise o resultado.')
            except Exception:
                LOGGER.exception('vision_inference_failed')
                result['warnings'].append('O detector falhou. A foto permanece disponível para revisão humana.')
    result['latency_ms'] = round((perf_counter() - started) * 1000, 3)
    return result
