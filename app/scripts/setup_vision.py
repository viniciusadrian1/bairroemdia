"""Download the pretrained ONNX detector pinned in provenance.json."""
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import urlopen


def main():
    destination = Path(__file__).resolve().parents[1] / 'modelos/vision'
    provenance = json.loads((destination / 'provenance.json').read_text(encoding='utf-8'))
    target = destination / provenance['file']
    expected = provenance['sha256']
    if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == expected:
        print('Modelo ONNX já instalado e verificado.')
        return
    with urlopen(provenance['source'] + provenance['file'], timeout=60) as response:
        if urlsplit(response.url).scheme != 'https':
            raise RuntimeError('Download sem HTTPS recusado.')
        body = response.read(55_000_001)
    if len(body) > 55_000_000 or hashlib.sha256(body).hexdigest() != expected:
        raise RuntimeError('Integridade do modelo inválida; arquivo não instalado.')
    temporary = target.with_suffix('.download')
    temporary.write_bytes(body)
    temporary.replace(target)
    print('Modelo ONNX instalado e SHA-256 verificado.')


if __name__ == '__main__':
    main()
