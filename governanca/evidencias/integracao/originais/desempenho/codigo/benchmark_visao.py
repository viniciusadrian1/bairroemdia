"""Medicao real do adapter ONNX sob lotes; sem HTTP, usuarios ou QPU.

Primeira corrida: python .../benchmark_visao.py
Para preservar corridas anteriores: python .../benchmark_visao.py --run-id outra-corrida
Requer OpenCV, NumPy e Pillow do modulo de Visao. Nao altera o aplicativo.
"""
from __future__ import annotations
import sys
sys.dont_write_bytecode = True

import argparse
import csv
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
import platform
import socket
import statistics
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parents[1]
VISION = PROJECT / '03-disciplinas/visao-computacional'
SOURCE = PROJECT / '02-solucao-integrada/app/backend/providers/vision.py'
MODEL = VISION / 'modelos/best.onnx'
BATCHES = (1, 4, 12)
THREADS = (1, 2, 4)
REPETITIONS = 3


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def csv_write(path, rows):
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def p95(values):
    return sorted(values)[math.ceil(.95 * len(values)) - 1]


class TimedLock:
    """Mantem a MESMA Lock do adapter; adiciona observacao monotonic/threadlocal."""
    def __init__(self, lock):
        self.lock = lock
        self.local = threading.local()

    def reset(self):
        self.local.wait_ms = 0.0
        self.local.hold_ms = 0.0
        self.local.entries = 0

    def __enter__(self):
        began = perf_counter()
        self.lock.acquire()
        acquired = perf_counter()
        self.local.wait_ms += (acquired - began) * 1000
        self.local.acquired = acquired
        self.local.entries += 1
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        ended = perf_counter()
        self.local.hold_ms += (ended - self.local.acquired) * 1000
        self.lock.release()
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', default='')
    args = parser.parse_args()
    base = ROOT / 'evidencias/visao-real'
    if args.run_id and not all(c.isalnum() or c in '-_' for c in args.run_id):
        raise ValueError('run-id deve conter apenas letras, numeros, - ou _.')
    out = base / 'corridas' / args.run_id if args.run_id else base
    if (out / 'manifesto.json').exists() or (out / 'chamadas.csv').exists():
        raise FileExistsError('Corrida preservada. Use --run-id com novo identificador.')
    out.mkdir(parents=True, exist_ok=True)
    frozen = out / 'fontes'
    frozen.mkdir(exist_ok=True)
    source_hash, model_hash = digest(SOURCE), digest(MODEL)
    provenance = json.loads((VISION / 'modelos/provenance.json').read_text(encoding='utf-8-sig'))
    assert provenance['sha256'] == model_hash
    (frozen / 'vision.py').write_bytes(SOURCE.read_bytes())
    assert digest(frozen / 'vision.py') == source_hash == digest(SOURCE)
    (frozen / 'provenance.json').write_bytes((VISION / 'modelos/provenance.json').read_bytes())
    inputs = []
    for path in sorted((VISION / 'dados/amostra_publica/test/images').glob('*.jpg')):
        data = path.read_bytes()
        inputs.append({'image_id': path.name, 'relative_to_project': path.relative_to(PROJECT).as_posix(),
                       'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data), 'data': data})
    assert len(inputs) == 12
    metadata = [{k: v for k, v in row.items() if k != 'data'} for row in inputs]
    dump(out / 'entradas.json', metadata)
    os.environ.update({'VISION_MODEL_PATH': str(MODEL), 'VISION_IMAGE_SIZE': '640',
                       'VISION_CONFIDENCE': '0.25', 'VISION_LABELS': 'pothole'})
    spec = importlib.util.spec_from_file_location('vision_frozen', frozen / 'vision.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    import cv2
    network_attempts = []
    original_connect = socket.socket.connect
    def forbidden_connect(*a, **kw):
        network_attempts.append(True)
        raise RuntimeError('Rede proibida neste experimento')
    socket.socket.connect = forbidden_connect
    try:
        t0 = perf_counter()
        warmup = module.analyze_image(inputs[0]['data'])
        warmup_wall_ms = (perf_counter() - t0) * 1000
        assert warmup['mode'] == 'model'
        # Referencia serial sem instrumentacao; todos os exemplos, fora das amostras.
        references = [module.analyze_image(row['data']) for row in inputs]
        assert all(row['mode'] == 'model' for row in references)
        dump(out / 'referencia-serial.json', references)
        lock = TimedLock(module.MODEL_LOCK)
        module.MODEL_LOCK = lock
        runs, calls = [], []
        config = [(n, t) for n in BATCHES for t in THREADS]
        for rep in range(REPETITIONS):
            # Tres ordens diferentes (normal, reversa, rotacionada); nao elimina ruido.
            ordered = config if rep == 0 else list(reversed(config)) if rep == 1 else config[4:] + config[:4]
            for n, threads in ordered:
                run_id = f'r{rep+1}-n{n}-t{threads}'
                with ThreadPoolExecutor(max_workers=threads) as pool:
                    barrier = threading.Barrier(threads)
                    prestarted = [pool.submit(barrier.wait) for _ in range(threads)]
                    for future in prestarted:
                        future.result(timeout=10)
                    def work(idx, submitted):
                        began = perf_counter()
                        lock.reset()
                        status, error, result = 'ok', '', {}
                        try:
                            result = module.analyze_image(inputs[idx]['data'])
                        except Exception as exc:
                            status, error = 'error', type(exc).__name__
                        ended = perf_counter()
                        same = result.get('detections') == references[idx]['detections']
                        return {'run_id': run_id, 'job_id': idx, 'image_id': inputs[idx]['image_id'],
                            'submitted_offset_ms': (submitted - batch_start) * 1000,
                            'start_offset_ms': (began - batch_start) * 1000,
                            'finish_offset_ms': (ended - batch_start) * 1000,
                            'harness_wait_ms': (began - submitted) * 1000,
                            'service_ms': (ended - began) * 1000,
                            'response_ms': (ended - submitted) * 1000,
                            'model_lock_wait_ms': lock.local.wait_ms,
                            'model_lock_hold_ms': lock.local.hold_ms,
                            'model_lock_entries': lock.local.entries,
                            'adapter_latency_ms': result.get('latency_ms', ''),
                            'mode': result.get('mode', ''), 'status': status, 'error': error,
                            'detections_equal_reference': same,
                            'detection_count': len(result.get('detections', []))}
                    batch_start = perf_counter()
                    pending = [pool.submit(work, i, perf_counter()) for i in range(n)]
                    result = [future.result(timeout=30) for future in pending]
                    batch_end = perf_counter()
                calls.extend(result)
                row = {'run_id': run_id, 'repetition': rep + 1, 'batch_calls': n, 'threads': threads,
                       'batch_wall_ms': (batch_end - batch_start) * 1000,
                       'errors': sum(r['status'] != 'ok' or r['mode'] != 'model' for r in result),
                       'reference_mismatches': sum(not r['detections_equal_reference'] for r in result)}
                for metric in ('harness_wait', 'service', 'response', 'model_lock_wait', 'model_lock_hold'):
                    values = [r[metric + '_ms'] for r in result]
                    row[metric + '_mean_ms'] = statistics.mean(values)
                    row[metric + '_p95_ms'] = p95(values)
                runs.append(row)
        summary = []
        for n, threads in config:
            selected = [r for r in runs if r['batch_calls'] == n and r['threads'] == threads]
            metrics = [k for k in selected[0] if k.endswith('_ms')]
            summary.append({'batch_calls': n, 'threads': threads,
                            **{k: statistics.mean(r[k] for r in selected) for k in metrics},
                            'batch_wall_min_ms': min(r['batch_wall_ms'] for r in selected),
                            'batch_wall_max_ms': max(r['batch_wall_ms'] for r in selected),
                            'response_p95_min_ms': min(r['response_p95_ms'] for r in selected),
                            'response_p95_max_ms': max(r['response_p95_ms'] for r in selected),
                            'errors': sum(r['errors'] for r in selected),
                            'reference_mismatches': sum(r['reference_mismatches'] for r in selected)})
        assert len(runs) == 27 and len(calls) == 153
        assert all(abs(r['harness_wait_ms'] + r['service_ms'] - r['response_ms']) < 1e-7 for r in calls)
        csv_write(out / 'chamadas.csv', calls)
        csv_write(out / 'execucoes.csv', runs)
        csv_write(out / 'resumo.csv', summary)
        unchanged = source_hash == digest(SOURCE) and model_hash == digest(MODEL)
        unchanged = unchanged and all(digest(PROJECT / r['relative_to_project']) == r['sha256'] for r in metadata)
        passed = unchanged and not network_attempts and all(r['mode'] == 'model' and r['detections_equal_reference'] and r['model_lock_entries'] == 1 for r in calls)
        manifest = {'status': 'passed' if passed else 'failed', 'executed_at_utc': datetime.now(timezone.utc).isoformat(),
            'evidence_kind': 'real_onnx_adapter_controlled_batch_load',
            'script_sha256': digest(Path(__file__)), 'source_sha256': source_hash,
            'source_relative_to_project': SOURCE.relative_to(PROJECT).as_posix(),
            'frozen_source': 'fontes/vision.py', 'model_sha256': model_hash,
            'model_relative_to_project': MODEL.relative_to(PROJECT).as_posix(),
            'original_inputs_unchanged': unchanged, 'python': sys.version, 'platform': platform.platform(),
            'processor': platform.processor(), 'logical_cpu_count': os.cpu_count(),
            'dependencies': {name: importlib.metadata.version(name) for name in ('numpy', 'Pillow')},
            'opencv': cv2.__version__, 'opencv_threads': cv2.getNumThreads(),
            'config': {'image_size': 640, 'confidence': .25, 'labels': 'pothole'},
            'measured_calls': len(calls), 'measured_runs': len(runs), 'warmup_calls': 1,
            'uninstrumented_reference_calls': 12, 'warmup_wall_ms': warmup_wall_ms,
            'batch_sizes': BATCHES, 'threads': THREADS, 'repetitions': REPETITIONS,
            'network_attempts': len(network_attempts), 'http_executed': False, 'quantum_executed': False,
            'percentile': 'nearest-rank; p95=maximo para n=1,4,12',
            'aggregation': 'media das metricas de tres repeticoes; nao e percentil agrupado',
            'lock_instrumentation': 'Proxy usa a mesma Lock original; mede espera/posse com perf_counter e threadlocal. Tem overhead nao subtraido.',
            'checks': ['153 chamadas e 27 lotes', 'deteccoes identicas a referencia serial sem instrumentacao',
                       'mode=model e uma entrada na Lock por chamada', 'fontes/pesos/imagens originais imutaveis',
                       'resposta=espera_harness+servico', 'nenhuma rede'],
            'limits': ['Demanda artificial em lotes, nao usuarios ou taxa de chegada controlada',
                       'Espera no executor separada da espera pela Lock real do adapter',
                       'Sem HTTP, LLM ou filas do servidor de producao',
                       '12 imagens externas; independencia do treino nao auditada; nao avalia acuracia',
                       'Tres repeticoes e maquina compartilhada; sem inferencia estatistica',
                       'Threads compartilham uma instancia de rede; nao equivalem a replicas em processos/GPU',
                       'Nao mede custo de decidir alocacao nem demonstra necessidade/ganho quantico']}
        manifest['output_sha256'] = {name: digest(out / name) for name in ('chamadas.csv', 'execucoes.csv', 'resumo.csv', 'entradas.json', 'referencia-serial.json')}
        dump(out / 'manifesto.json', manifest)
        print(json.dumps({'status': manifest['status'], 'measured_calls': len(calls), 'measured_runs': len(runs), 'out': str(out)}, ensure_ascii=False))
        for r in summary:
            print(f"n={r['batch_calls']:2} t={r['threads']} lote={r['batch_wall_ms']:.2f}ms "
                  f"p95resposta={r['response_p95_ms']:.2f}ms p95lock={r['model_lock_wait_p95_ms']:.2f}ms "
                  f"lockmedia={r['model_lock_wait_mean_ms']:.2f}ms erros={r['errors']} divergencias={r['reference_mismatches']}")
        if not passed:
            raise RuntimeError('Verificacoes falharam; resultados nao aprovados, consulte manifesto.')
    finally:
        socket.socket.connect = original_connect


if __name__ == '__main__':
    main()
