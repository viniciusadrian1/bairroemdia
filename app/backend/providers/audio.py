"""Real, local YAMNet SavedModel inference in an isolated bounded subprocess.

The API environment imports only stdlib here. NumPy/SciPy/LiteRT live in the
model's separate venv. No upload, audio CLI argument or persistent audio file.
See modelos/yamnet/README.md for provenance, averaging and uncalibrated rules.
"""
import csv
from functools import lru_cache
import hashlib
import io
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import sys
from threading import BoundedSemaphore
from time import perf_counter

APP_ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = APP_ROOT / 'modelos' / 'yamnet'
MODEL_VERSION = 'google-yamnet-savedmodel-1'
# Identity of the exact official compressed archive; every extracted file is checked too.
MODEL_SHA256 = 'b80da2a1a56926fb0767205051a200dd7b3beaf3ea1ea126c42a53943996e5e0'
LABELS_SHA256 = 'cdf24d193e196d9e95912a2667051ae203e92a2ba09449218ccb40ef787c6df2'
SAVEDMODEL_FILES = {
    'saved_model.pb': (3176321, '672af6e1e34fe15a42d45d70217fd39f97e10aef9b0effbf9b0bf7826fccd462'),
    'variables/variables.data-00000-of-00001': (15077564, 'd6753f22f173b2a8b1ce78918eaae79bf0a41ca61f4cfe9a1b948c97ff094ddc'),
    'variables/variables.index': (7400, '0bc2ca10e56e8a71b96a2cad26adbbabff927e9344fbd2df8ae7275ddf76ae1e'),
    'assets/yamnet_class_map.csv': (14096, LABELS_SHA256),
}
MAX_BYTES = 3_000_000
MIN_SECONDS = 1
MAX_SECONDS = 15
SAMPLE_RATE = 16000
WINDOW_SAMPLES = 15600
HOP_SAMPLES = 7680
MIN_SCORE = .35  # heuristic only; NOT a calibrated probability or accuracy
TARGET_MARGIN = .05  # ambiguity between bell and knock, not hierarchical classes
DECISION_VERSION = 'temporal-v1'
TARGETS = {'Doorbell': 'campainha', 'Ding-dong': 'campainha', 'Knock': 'batida'}
WORKER_TIMEOUT = 30
_WORKER_SLOT = BoundedSemaphore(1)


class AudioUnavailable(RuntimeError):
    """Missing/incompatible model runtime or bounded inference failure."""


def _wav_header(raw):
    """Validate byte counts and real sample duration BEFORE numerical decoding."""
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_BYTES:
        raise ValueError('Envie WAV PCM16 de até 3 MB.')
    if len(raw) < 44 or raw[:4] != b'RIFF' or raw[8:12] != b'WAVE':
        raise ValueError('Use WAV RIFF PCM16 válido, mono ou estéreo.')
    if struct.unpack_from('<I', raw, 4)[0] + 8 != len(raw):
        raise ValueError('Tamanho RIFF não corresponde ao arquivo recebido.')
    position, fmt, audio_range = 12, None, None
    while position < len(raw):
        if position + 8 > len(raw): raise ValueError('Cabeçalho WAV incompleto.')
        chunk_id, size = struct.unpack_from('<4sI', raw, position)
        start, end = position + 8, position + 8 + size
        if end > len(raw): raise ValueError('Chunk WAV truncado ou tamanho adulterado.')
        if chunk_id == b'fmt ':
            if fmt is not None or size < 16: raise ValueError('Formato WAV inválido.')
            fmt = struct.unpack_from('<HHIIHH', raw, start)
        elif chunk_id == b'data':
            if audio_range is not None: raise ValueError('Use um único bloco de áudio WAV.')
            audio_range = (start, end)
        position = end + (size & 1)
    if position != len(raw) or fmt is None or audio_range is None:
        raise ValueError('WAV sem metadados/bloco PCM completos.')
    encoding, channels, rate, byte_rate, block_align, bits = fmt
    if encoding != 1 or bits != 16 or channels not in (1, 2) or not 8000 <= rate <= 48000:
        raise ValueError('Use WAV PCM16 mono/estéreo entre 8 e 48 kHz.')
    if block_align != channels * 2 or byte_rate != rate * block_align:
        raise ValueError('Metadados PCM inconsistentes.')
    byte_count = audio_range[1] - audio_range[0]
    if byte_count % block_align: raise ValueError('Amostra PCM incompleta.')
    frames = byte_count // block_align
    duration = frames / rate
    if not MIN_SECONDS <= duration <= MAX_SECONDS:
        raise ValueError('O áudio precisa durar entre 1 e 15 segundos.')
    return {'duration_seconds': duration, 'source_sample_rate': rate,
            'channels': channels, 'frames': frames, 'data_start': audio_range[0], 'data_end': audio_range[1]}


def _decode_wav(raw):
    metadata = _wav_header(raw)
    import numpy as np
    # Cast before summing: two int16 channels must not overflow.
    samples = np.frombuffer(raw[metadata['data_start']:metadata['data_end']], dtype='<i2').astype(np.float32)
    samples = samples.reshape(-1, metadata['channels']).mean(axis=1) / 32768.0
    rate = metadata['source_sample_rate']
    if rate != SAMPLE_RATE:
        from scipy.signal import resample_poly
        divisor = math.gcd(rate, SAMPLE_RATE)
        samples = resample_poly(samples, SAMPLE_RATE // divisor, rate // divisor)
    wanted = round(metadata['frames'] * SAMPLE_RATE / rate)
    samples = np.clip(samples[:wanted], -1.0, 1.0).astype(np.float32)
    if samples.size != wanted or not np.isfinite(samples).all():
        raise ValueError('Não foi possível normalizar o áudio recebido.')
    return samples, metadata


def _paths():
    # Keep the Windows prefix short enough for TensorFlow's bundled C headers.
    default_python = APP_ROOT.parent / '.venv-audio' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    return (Path(os.getenv('YAMNET_MODEL_PATH', str(MODEL_DIR / 'saved_model'))),
            Path(os.getenv('YAMNET_LABELS_PATH', str(MODEL_DIR / 'yamnet_class_map.csv'))),
            Path(os.getenv('YAMNET_PYTHON', str(default_python))))


@lru_cache(maxsize=8)
def _checked_hash(path, modified_ns, size, expected):
    digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    if digest != expected: raise AudioUnavailable('Integridade do YAMNet diverge do export oficial fixado.')
    return digest


def _assets():
    model, labels, python = _paths()
    try:
        if not model.is_dir():
            raise AudioUnavailable('Modelo YAMNet ausente/incompleto. Execute scripts/setup_yamnet.py.')
        if not labels.is_file() or labels.stat().st_size > 65536:
            raise AudioUnavailable('Mapa oficial das 521 classes indisponível.')
        checked_files = [(labels, LABELS_SHA256)]
        for relative, (size, digest) in SAVEDMODEL_FILES.items():
            path = model / relative
            if not path.is_file() or path.stat().st_size != size:
                raise AudioUnavailable('SavedModel YAMNet incompleto. Execute scripts/setup_yamnet.py.')
            checked_files.append((path, digest))
        for path, expected in checked_files:
            stat = path.stat()
            _checked_hash(str(path.resolve()), stat.st_mtime_ns, stat.st_size, expected)
        if not python.is_file():
            raise AudioUnavailable('Runtime isolado ausente. Execute setup_yamnet.py --install-runtime.')
        return model, labels, python
    except OSError as exc:
        raise AudioUnavailable('Arquivos do modelo não puderam ser lidos.') from exc


def model_status():
    from backend.providers.audio_sources import SOURCE_PROFILE_VERSION
    try:
        _assets()
        return {'available': True, 'loaded': False, 'model_version': MODEL_VERSION, 'decision_version': DECISION_VERSION,
                'source_profile_version': SOURCE_PROFILE_VERSION,
                'reason': 'Artefatos verificados e executável presente; runtime e inferência só são confirmados ao analisar áudio.'}
    except AudioUnavailable as exc:
        return {'available': False, 'loaded': False, 'model_version': MODEL_VERSION,
                'decision_version': DECISION_VERSION, 'source_profile_version': SOURCE_PROFILE_VERSION, 'reason': str(exc)}


def _run_model(raw):
    _model, _labels, python = _assets()
    if not _WORKER_SLOT.acquire(timeout=1):
        raise AudioUnavailable('Análise sonora ocupada. Aguarde e tente novamente.')
    try:
        environment = os.environ.copy()
        environment.update(OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', TF_CPP_MIN_LOG_LEVEL='2',
                           PYTHONIOENCODING='utf-8', PYTHONUTF8='1')
        process = subprocess.run([str(python.resolve()), str(Path(__file__).resolve()), '--worker'],
                                 input=raw, capture_output=True, timeout=WORKER_TIMEOUT,
                                 creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                                 env=environment)
        if process.returncode != 0 or len(process.stdout) > 512 * 1024:
            raise AudioUnavailable('O runtime local YAMNet falhou. Confira setup_yamnet.py --verify.')
        result = json.loads(process.stdout)
        if not isinstance(result, dict): raise AudioUnavailable('Resposta inválida do runtime sonoro.')
        return result
    except subprocess.TimeoutExpired as exc:
        raise AudioUnavailable('A análise sonora excedeu 30 segundos e foi encerrada.') from exc
    except (OSError, ValueError) as exc:
        raise AudioUnavailable('Não foi possível executar o runtime sonoro local.') from exc
    finally:
        _WORKER_SLOT.release()


def _validated_scores(output):
    labels, scores = output.get('labels'), output.get('scores')
    if not isinstance(labels, list) or not isinstance(scores, list) or len(labels) != 521 or len(scores) != 521:
        raise AudioUnavailable('Saída YAMNet incompatível com 521 classes.')
    if any(not isinstance(label, str) or not label for label in labels) or len(set(labels)) != 521:
        raise AudioUnavailable('Rótulos YAMNet inválidos.')
    if not all(name in labels for name in TARGETS): raise AudioUnavailable('Classes de interesse ausentes.')
    if any(isinstance(s, bool) or not isinstance(s, (int, float)) or not math.isfinite(s) or not 0 <= s <= 1 for s in scores):
        raise AudioUnavailable('Escores YAMNet inválidos; nenhuma previsão foi aceita.')
    if output.get('model_sha256') != MODEL_SHA256 or output.get('model_version') != MODEL_VERSION:
        raise AudioUnavailable('Identidade do modelo difere do export oficial fixado.')
    return labels, scores


def _validated_frames(output, metadata):
    frames = output.get('frame_scores')
    samples = round(metadata['frames'] * SAMPLE_RATE / metadata['source_sample_rate'])
    expected = max(1, math.ceil((samples - WINDOW_SAMPLES) / HOP_SAMPLES) + 1)
    if (not isinstance(frames, list) or not 1 <= len(frames) <= 31 or len(frames) != expected or
            type(output.get('frame_count')) is not int or output['frame_count'] != expected):
        raise AudioUnavailable('Quantidade de janelas YAMNet incompatível com a duração real.')
    for frame in frames:
        if not isinstance(frame, list) or len(frame) != 521:
            raise AudioUnavailable('Cada janela YAMNet deve conter 521 escores.')
        if any(isinstance(s, bool) or not isinstance(s, (int, float)) or not math.isfinite(s) or not 0 <= s <= 1 for s in frame):
            raise AudioUnavailable('Janela YAMNet contém escores inválidos.')
    for index, mean_score in enumerate(output['scores']):
        actual_mean = math.fsum(frame[index] for frame in frames) / len(frames)
        if abs(actual_mean - mean_score) > 1e-6:
            raise AudioUnavailable('Média YAMNet diverge das janelas fornecidas.')
    return frames


def _top_classes(labels, scores):
    ranking = sorted(range(521), key=lambda index: scores[index], reverse=True)
    return [{'label': labels[index], 'score': float(scores[index])} for index in ranking[:5]]


def analyze_audio(raw: bytes) -> dict:
    from backend.providers.audio_sources import classify_source
    started = perf_counter()
    metadata = _wav_header(raw)
    output = _run_model(raw)
    labels, scores = _validated_scores(output)
    frames = _validated_frames(output, metadata)
    ranking = sorted(range(521), key=lambda index: scores[index], reverse=True)
    top = ranking[0]
    confidence = float(scores[top])
    label = TARGETS.get(labels[top], 'outro')
    warnings = ['Escores YAMNet não são probabilidades calibradas nem acurácia; limiares são heurísticos, sem calibração local.',
                'Análise educacional de conteúdo sonoro; não mede decibéis, volume excessivo ou infração e não substitui alertas de emergência.']
    mean_warnings = []
    if confidence < MIN_SCORE:
        label = 'incerto'
        mean_warnings.append('Maior escore médio abaixo de 0,35; resultado inconclusivo.')
    elif label in ('campainha', 'batida'):
        competing = max(scores[index] for index, name in enumerate(labels)
                        if name in TARGETS and TARGETS[name] != label)
        if confidence - competing < TARGET_MARGIN:
            label = 'incerto'
            mean_warnings.append('Campainha e batida competem na média com diferença menor que 0,05.')
    mean_top_classes = _top_classes(labels, scores)
    decisive_scores = scores
    candidates = []
    for frame_index, frame in enumerate(frames):
        winner = max(range(521), key=lambda index: frame[index])
        target = TARGETS.get(labels[winner])
        if target is None or frame[winner] < MIN_SCORE:
            continue
        competing = max(frame[index] for index, name in enumerate(labels)
                        if name in TARGETS and TARGETS[name] != target)
        if frame[winner] - competing < TARGET_MARGIN:
            continue
        candidates.append({'frame_index': frame_index, 'label': target, 'score': float(frame[winner])})
    event_windows = [{'start_seconds': row['frame_index'] * HOP_SAMPLES / SAMPLE_RATE,
                      'end_seconds': min(metadata['duration_seconds'], (row['frame_index'] * HOP_SAMPLES + WINDOW_SAMPLES) / SAMPLE_RATE),
                      'label': row['label'], 'score': row['score']} for row in candidates]
    if candidates:
        decisive = max(candidates, key=lambda row: row['score'])
        label, confidence = decisive['label'], decisive['score']
        decisive_scores = frames[decisive['frame_index']]
        other_peaks = [row['score'] for row in candidates if row['label'] != label]
        if other_peaks and confidence - max(other_peaks) < TARGET_MARGIN:
            label = 'incerto'
            warnings.append('Janelas de campainha e batida competem com picos separados por menos de 0,05.')
        warnings.append('Decisão por janela de evento curto; não representa o som dominante do arquivo. Intervalos são janelas de análise, não limites exatos do som.')
    elif label in ('campainha', 'batida'):
        label = 'incerto'
        warnings.append('A média sugere um alvo, mas nenhuma janela cumpriu todos os critérios temporais.')
    else:
        warnings.extend(mean_warnings)
    if metadata['channels'] == 2: warnings.append('Áudio estéreo convertido em mono por média dos canais.')
    if metadata['source_sample_rate'] != SAMPLE_RATE:
        warnings.append(f"Áudio reamostrado de {metadata['source_sample_rate']} Hz para 16000 Hz.")
    return {'mode': 'yamnet', 'model_version': output['model_version'], 'model_sha256': output['model_sha256'],
            'decision_version': DECISION_VERSION, 'aggregation': 'target_event_windows',
            'label': label, 'confidence': confidence,
            'top_classes': _top_classes(labels, decisive_scores), 'mean_top_classes': mean_top_classes,
            'neighborhood_source': classify_source(labels, scores),
            'event_windows': event_windows,
            'duration_seconds': metadata['duration_seconds'], 'sample_rate': SAMPLE_RATE,
            'latency_ms': round((perf_counter() - started) * 1000, 3), 'warnings': warnings}


def _worker_infer(raw):
    import numpy as np
    import tensorflow as tf
    tf.config.threading.set_intra_op_parallelism_threads(2)
    tf.config.threading.set_inter_op_parallelism_threads(1)
    model, labels_path, _python = _assets()
    samples, _ = _decode_wav(raw)
    with labels_path.open(encoding='utf-8', newline='') as file:
        rows = list(csv.DictReader(file))
    if len(rows) != 521 or [int(row['index']) for row in rows] != list(range(521)):
        raise AudioUnavailable('Índices do mapa YAMNet inválidos.')
    network = tf.saved_model.load(str(model))
    # The official graph owns its log-Mel preprocessing, framing and zero padding.
    frame_scores = network(tf.constant(samples, dtype=tf.float32))[0].numpy()
    window_count = max(1, math.ceil((len(samples) - WINDOW_SAMPLES) / HOP_SAMPLES) + 1)
    if frame_scores.shape != (window_count, 521) or frame_scores.dtype != np.float32:
        raise AudioUnavailable('Contrato SavedModel incompatível com o export oficial fixado.')
    if not np.isfinite(frame_scores).all() or (frame_scores < 0).any() or (frame_scores > 1).any():
        raise AudioUnavailable('Modelo produziu escores inválidos.')
    return {'labels': [row['display_name'] for row in rows],
            'scores': np.asarray(frame_scores, dtype=np.float64).mean(axis=0).tolist(),
            'frame_scores': frame_scores.tolist(), 'frame_count': window_count,
            'model_version': MODEL_VERSION, 'model_sha256': MODEL_SHA256}


if __name__ == '__main__':
    if sys.argv[1:] != ['--worker']:
        raise SystemExit('Este módulo só executa como --worker local via stdin.')
    try:
        result = _worker_infer(sys.stdin.buffer.read(MAX_BYTES + 1))
        sys.stdout.write(json.dumps(result, ensure_ascii=False, allow_nan=False))
    except Exception as error:
        sys.stderr.write(f'YAMNet worker failed: {type(error).__name__}: {error}\n')
        raise SystemExit(1)
