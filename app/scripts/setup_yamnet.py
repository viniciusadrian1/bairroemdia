"""Download hash-pinned official YAMNet assets; optionally install isolated runtime.

python scripts/setup_yamnet.py --install-runtime --verify
No user audio is uploaded. Verification uses explicitly synthetic silence only.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
from io import BytesIO, StringIO
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tarfile
from urllib.parse import urlsplit
from urllib.request import urlopen
import venv
import wave
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / 'modelos' / 'yamnet'
RUNTIME_DIR = ROOT.parent / '.venv-audio'
SAVEDMODEL_URL = 'https://tfhub.dev/google/yamnet/1?tf-hub-format=compressed'
FILES = {
    'yamnet.tflite': ('https://tfhub.dev/google/lite-model/yamnet/classification/tflite/1?lite-format=tflite',
                      '10c95ea3eb9a7bb4cb8bddf6feb023250381008177ac162ce169694d05c317de'),
    'yamnet_class_map.csv': ('https://raw.githubusercontent.com/tensorflow/models/master/research/audioset/yamnet/yamnet_class_map.csv',
                            'cdf24d193e196d9e95912a2667051ae203e92a2ba09449218ccb40ef787c6df2'),
    'LICENSE': ('https://raw.githubusercontent.com/tensorflow/models/master/LICENSE',
                '5b17814bf0de8cf65069bc6d7cc38cff19fcaa864d243423ad3ef3db01b52385'),
}


def download_baseline_assets():
    DESTINATION.mkdir(parents=True, exist_ok=True)
    records = []
    for name, (url, expected) in FILES.items():
        path = DESTINATION / name
        body = path.read_bytes() if path.is_file() else b''
        if hashlib.sha256(body).hexdigest() != expected:
            with urlopen(url, timeout=45) as response:
                if urlsplit(response.url).scheme != 'https': raise RuntimeError('Download sem HTTPS recusado.')
                body = response.read(20 * 1024 * 1024 + 1)
            if len(body) > 20 * 1024 * 1024 or hashlib.sha256(body).hexdigest() != expected:
                raise RuntimeError(f'{name}: hash diverge do artefato oficial auditado; nada foi substituído.')
            temporary = path.with_suffix(path.suffix + '.download')
            temporary.write_bytes(body)
            temporary.replace(path)
        records.append({'file': name, 'source_url': url, 'sha256': expected, 'bytes': len(body)})
    model_bytes = (DESTINATION / 'yamnet.tflite').read_bytes()
    with zipfile.ZipFile(BytesIO(model_bytes)) as archive:
        embedded = archive.read('yamnet_label_list.txt').decode('utf-8').splitlines()
    rows = list(csv.DictReader(StringIO((DESTINATION / 'yamnet_class_map.csv').read_text(encoding='utf-8'))))
    if len(rows) != 521 or [row['display_name'] for row in rows] != embedded:
        raise RuntimeError('CSV não corresponde às 521 classes embutidas no modelo.')
    license_text = b'Apache License. Version 2.0 http://www.apache.org/licenses/LICENSE-2.0.'
    if license_text not in model_bytes: raise RuntimeError('Licença Apache não encontrada nos metadados esperados.')
    manifest = {'model': 'YAMNet', 'model_version': 'google-yamnet-classification-tflite-1',
                'retrieved_at': datetime.now(timezone.utc).isoformat(), 'files': records,
                'license': 'Apache-2.0', 'license_evidence': 'Explicit Apache license string embedded in official TFLite metadata; LICENSE from tensorflow/models.',
                'input': {'dtype': 'float32', 'shape': [15600], 'sample_rate': 16000, 'channels': 1, 'range': [-1, 1]},
                'output': {'dtype': 'float32', 'shape': [1, 521]}, 'labels_match_embedded': True,
                'model_modified': False, 'trained_by_group': False,
                'source_documentation': 'https://github.com/tensorflow/tflite-support/tree/master/tensorflow_lite_support/examples/task/audio/desktop'}
    (DESTINATION / 'baseline-tflite-manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
    return manifest


def download_assets():
    download_baseline_assets()
    sys.path.insert(0, str(ROOT))
    from backend.providers.audio import MODEL_VERSION, MODEL_SHA256, SAVEDMODEL_FILES
    archive_path = DESTINATION / '.deps' / 'yamnet-savedmodel-1.tar.gz'
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    archive = archive_path.read_bytes() if archive_path.is_file() else b''
    if hashlib.sha256(archive).hexdigest() != MODEL_SHA256:
        with urlopen(SAVEDMODEL_URL, timeout=45) as response:
            if urlsplit(response.url).scheme != 'https': raise RuntimeError('Download sem HTTPS recusado.')
            archive = response.read(20 * 1024 * 1024 + 1)
        if len(archive) > 20 * 1024 * 1024 or hashlib.sha256(archive).hexdigest() != MODEL_SHA256:
            raise RuntimeError('SavedModel diverge do hash oficial auditado; download rejeitado.')
        archive_path.write_bytes(archive)
    # Only four fixed, hash-pinned regular files are extracted; no archive paths
    # are used for arbitrary filesystem operations, and links are never accepted.
    payloads = {}
    with tarfile.open(fileobj=BytesIO(archive), mode='r:gz') as tar:
        for name, (expected_size, expected_hash) in SAVEDMODEL_FILES.items():
            member = tar.getmember(name)
            if not member.isfile() or member.size != expected_size:
                raise RuntimeError(f'SavedModel contém arquivo inesperado: {name}')
            body = tar.extractfile(member).read(expected_size + 1)
            if len(body) != expected_size or hashlib.sha256(body).hexdigest() != expected_hash:
                raise RuntimeError(f'SavedModel: integridade inválida: {name}')
            payloads[name] = body
    for name, body in payloads.items():
        path = DESTINATION / 'saved_model' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.is_file() or path.read_bytes() != body:
            temporary = path.with_suffix(path.suffix + '.download')
            temporary.write_bytes(body); temporary.replace(path)
    manifest = {'model': 'YAMNet', 'format': 'TensorFlow SavedModel', 'model_version': MODEL_VERSION,
                'model_sha256': MODEL_SHA256, 'source_url': SAVEDMODEL_URL, 'archive_bytes': len(archive),
                'retrieved_at': datetime.now(timezone.utc).isoformat(), 'license': 'Apache-2.0',
                'license_source': FILES['LICENSE'][0],
                'files': [{'file': name, 'bytes': size, 'sha256': digest} for name, (size, digest) in SAVEDMODEL_FILES.items()],
                'input': {'dtype': 'float32', 'shape': ['samples'], 'sample_rate': 16000, 'channels': 1, 'range': [-1, 1]},
                'scores_output': {'dtype': 'float32', 'shape': ['frames', 521]},
                'frame_window_samples': 15600, 'frame_hop_samples': 7680,
                'model_modified': False, 'trained_by_group': False, 'decision_version': 'temporal-v1',
                'source_documentation': 'https://www.tensorflow.org/hub/tutorials/yamnet',
                'baseline': 'baseline-tflite-manifest.json; original TFLite and diagnostic outputs retained.'}
    (DESTINATION / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    return manifest


def runtime_python():
    return RUNTIME_DIR / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')


def install_runtime():
    if not runtime_python().is_file():
        venv.EnvBuilder(with_pip=True, system_site_packages=False).create(RUNTIME_DIR)
    # Explicit handles retain pip diagnostics under CREATE_NO_WINDOW on Windows.
    log_path = DESTINATION / 'runtime-install.log'
    with log_path.open('w', encoding='utf-8') as log:
        process = subprocess.run([str(runtime_python()), '-m', 'pip', 'install', '--only-binary=:all:',
                                  '-r', str(ROOT / 'requirements-audio.txt')], stdout=log, stderr=subprocess.STDOUT,
                                 creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    if process.returncode:
        print(log_path.read_text(encoding='utf-8', errors='replace')[-4000:], file=sys.stderr)
        raise RuntimeError(f'Instalação isolada falhou; detalhes em {log_path}.')
    print('Runtime isolado instalado; detalhes em ' + str(log_path), flush=True)


def verify():
    sys.path.insert(0, str(ROOT))
    from backend.providers.audio import analyze_audio, model_status
    stream = BytesIO()
    with wave.open(stream, 'wb') as wav:
        wav.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
        wav.writeframes(struct.pack('<h', 0) * 16000)
    result = analyze_audio(stream.getvalue())
    report = {'verified_at': datetime.now(timezone.utc).isoformat(), 'status': model_status(),
              'input': 'SYNTHETIC: 1 second of digital silence; not microphone or smartphone evidence.',
              'actual_model_inference': True, 'accuracy_measured': False, 'result': result}
    destination = DESTINATION / 'verification.json'
    baseline = DESTINATION / 'baseline-tflite-verification.json'
    if destination.is_file() and not baseline.is_file():
        previous = json.loads(destination.read_text(encoding='utf-8'))
        if previous.get('result', {}).get('model_version') == 'google-yamnet-classification-tflite-1':
            baseline.write_bytes(destination.read_bytes())
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install-runtime', action='store_true')
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    manifest = download_assets()
    print(json.dumps({'assets_verified': True, 'model_version': manifest['model_version']}), flush=True)
    if args.install_runtime: install_runtime()
    if args.verify:
        report = verify()
        print(json.dumps({'real_inference_completed': True, 'input': report['input'],
                          'top_classes': report['result']['top_classes'], 'latency_ms': report['result']['latency_ms']}))


if __name__ == '__main__': main()
