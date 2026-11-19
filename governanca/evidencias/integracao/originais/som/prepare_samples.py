"""Fetch three preselected CC0 public previews; no inference or sample replacement.

The selection was made from source descriptions, before any new-source inference.
All previews are converted in full to PCM16/mono/16k, without normalization/cuts.
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import wave

import imageio_ffmpeg
import requests

ROOT = Path(__file__).resolve().parent
SELECTION = [
    ('199929', 'thedapperdan', 'furadeira'),
    ('42097', 'fauxpress', 'obra_ferramentas'),
    ('644772', 'Mamradrohliki', 'musica'),
]


def main():
    manifest_path = ROOT / 'manifest.json'
    if manifest_path.exists():
        raise SystemExit('Manifest already frozen; reuse the existing samples.')
    (ROOT / 'sources').mkdir(exist_ok=True)
    (ROOT / 'wav').mkdir(exist_ok=True)
    manifest = {'selection': 'Three public CC0 clips selected by source description before inference.',
                'purpose': 'Exploratory technical demonstration, not independent holdout or general accuracy.',
                'transform': 'Entire MP3 preview to PCM16 mono 16000Hz, no trimming or gain normalization.',
                'files': []}
    for sound_id, author, expected in SELECTION:
        url = f'https://freesound.org/people/{author}/sounds/{sound_id}/'
        page = requests.get(url, timeout=45)
        page.raise_for_status()
        if 'creativecommons.org/publicdomain/zero/1.0' not in page.text:
            raise RuntimeError('CC0 license not confirmed: ' + url)
        (ROOT / 'sources' / f'{sound_id}.html').write_text(page.text, encoding='utf-8')
        previews = re.findall(r'https://[^\s"<>]+-hq\.mp3', page.text)
        preview = next((p for p in previews if f'/{sound_id}_' in p), None)
        if not preview:
            raise RuntimeError('No matching public HQ preview: ' + url)
        content = requests.get(preview, timeout=45)
        content.raise_for_status()
        mp3 = ROOT / 'sources' / f'{sound_id}.mp3'
        mp3.write_bytes(content.content)
        wav = ROOT / 'wav' / f'{expected}-{sound_id}.wav'
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-y', '-v', 'error', '-i', str(mp3),
                        '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', str(wav)], check=True)
        with wave.open(str(wav)) as decoded:
            duration = decoded.getnframes() / decoded.getframerate()
        if not 1 <= duration <= 15:
            raise RuntimeError('Sample outside supported duration; do not silently trim.')
        manifest['files'].append({'id': sound_id, 'author': author, 'source_url': url,
                                  'preview_url': preview, 'license': 'CC0-1.0', 'expected': expected,
                                  'path': str(wav.relative_to(ROOT)), 'duration_seconds': duration,
                                  'source_sha256': hashlib.sha256(content.content).hexdigest(),
                                  'wav_sha256': hashlib.sha256(wav.read_bytes()).hexdigest()})
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
