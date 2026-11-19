"""Carga limitada no endpoint local /vision; nao cria relatos nem altera dados.

Uma corrida por diretorio. --output-dir permite preservar corridas anteriores.
Somente biblioteca padrao; 51 chamadas medidas e uma de aquecimento.
"""
import argparse
import base64
import csv
import hashlib
import json
import platform
import statistics
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from urllib.error import HTTPError
from urllib.request import Request, ProxyHandler, build_opener

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parents[1]
URL = "http://127.0.0.1:8000"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def request(path, body=None):
    req = Request(URL + path, data=body, headers={"Content-Type": "application/json"})
    with build_opener(ProxyHandler({})).open(req, timeout=15) as response:
        return response.status, json.load(response)


def csv_write(path, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "evidencias" / "http-visao-real")
    out = parser.parse_args().output_dir.resolve()
    out.relative_to(ROOT.resolve())
    if out.exists() and any(out.iterdir()):
        raise RuntimeError("Diretorio ja contem dados; use --output-dir para preservar a corrida anterior.")
    out.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).isoformat()
    _, health = request("/health")
    paths = sorted((PROJECT / "03-disciplinas/visao-computacional/dados/amostra_publica/test/images").glob("*.jpg"))[:12]
    assert len(paths) == 12
    inputs = [{"path": p.relative_to(PROJECT).as_posix(), "sha256": digest(p)} for p in paths]
    payloads = [json.dumps({"image_base64": base64.b64encode(p.read_bytes()).decode("ascii")}).encode() for p in paths]
    warm_status, warm_result = request("/vision", payloads[0])
    assert warm_status == 200 and warm_result["mode"] == "model"
    rows, runs = [], []
    for repetition in range(3):
        order = (1, 4, 12) if repetition % 2 == 0 else (12, 4, 1)
        for count in order:
            run_id = f"r{repetition + 1}-n{count}-http4"
            with ThreadPoolExecutor(max_workers=4) as pool:
                barrier = threading.Barrier(4)
                warm = [pool.submit(barrier.wait) for _ in range(4)]
                for future in warm:
                    future.result(timeout=5)

                def work(index, submitted):
                    began = perf_counter()
                    status, result, error = 0, {}, ""
                    try:
                        status, result = request("/vision", payloads[index])
                    except HTTPError as exc:
                        status, error = exc.code, type(exc).__name__
                    except Exception as exc:
                        error = type(exc).__name__
                    ended = perf_counter()
                    return {"run_id": run_id, "image_index": index, "http_status": status,
                        "mode": result.get("mode", "error"), "error_type": error,
                        "client_queue_ms": (began - submitted) * 1000,
                        "http_elapsed_ms": (ended - began) * 1000,
                        "response_from_submit_ms": (ended - submitted) * 1000,
                        "adapter_reported_ms": result.get("latency_ms", ""),
                        "detections_sha256": hashlib.sha256(json.dumps(result.get("detections", []), sort_keys=True).encode()).hexdigest()}

                begin = perf_counter()
                futures = [pool.submit(work, i, perf_counter()) for i in range(count)]
                values = [future.result(timeout=20) for future in futures]
                elapsed = (perf_counter() - begin) * 1000
            rows.extend(values)
            runs.append({"run_id": run_id, "batch_calls": count, "client_threads": 4,
                "batch_wall_ms": elapsed,
                "http_mean_ms": statistics.mean(r["http_elapsed_ms"] for r in values),
                "http_max_ms": max(r["http_elapsed_ms"] for r in values),
                "response_max_ms": max(r["response_from_submit_ms"] for r in values),
                "client_queue_mean_ms": statistics.mean(r["client_queue_ms"] for r in values),
                "adapter_reported_mean_ms": statistics.mean(float(r["adapter_reported_ms"]) for r in values if r["mode"] == "model"),
                "errors": sum(r["http_status"] != 200 or r["mode"] != "model" for r in values)})
    csv_write(out / "chamadas.csv", rows)
    csv_write(out / "execucoes.csv", runs)
    summary = []
    for count in (1, 4, 12):
        group = [r for r in runs if r["batch_calls"] == count]
        metrics = [key for key in group[0] if key.endswith("_ms")]
        summary.append({"batch_calls": count, "client_threads": 4,
            **{key: statistics.mean(r[key] for r in group) for key in metrics},
            "batch_wall_min_ms": min(r["batch_wall_ms"] for r in group),
            "batch_wall_max_ms": max(r["batch_wall_ms"] for r in group),
            "errors": sum(r["errors"] for r in group)})
    csv_write(out / "resumo.csv", summary)
    (out / "entradas.json").write_text(json.dumps(inputs, indent=2), encoding="utf-8")
    valid = len(rows) == 51 and all(r["http_status"] == 200 and r["mode"] == "model" for r in rows)
    manifest = {"status": "passed" if valid else "failed", "started_at_utc": started,
        "finished_at_utc": datetime.now(timezone.utc).isoformat(), "base_url": URL,
        "health_observed": health, "script_sha256": digest(Path(__file__)),
        "environment": platform.platform(), "python": platform.python_version(),
        "measured_calls": len(rows), "measured_runs": len(runs), "warmup_calls": 1,
        "endpoint": "POST /vision", "writes_reports": False,
        "evidence_kind": "real_local_http_vision_controlled_batch",
        "server_source_hash_exported": False, "server_model_hash_exported": False,
        "limits": ["Lotes artificiais e 4 threads de cliente; nao sao usuarios reais ou taxa aberta",
                   "Espera no cliente nao e fila do servidor; tempo HTTP inclui transporte/servidor",
                   "latency_ms do adapter inclui espera interna; nao isola inferencia",
                   "Servidor preexistente compartilhado; health nao comprova versao/hash carregados",
                   "Tres repeticoes descritivas; nenhuma inferencia estatistica ou vantagem quantica"],
        "output_sha256": {p.name: digest(p) for p in out.iterdir() if p.suffix in (".csv", ".json")}}
    (out / "manifesto.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"manifest": manifest, "summary": summary}, indent=2, ensure_ascii=False))
    if not valid:
        raise RuntimeError("Uma ou mais chamadas falharam; resultados nao devem ser tratados como aprovados.")


if __name__ == "__main__":
    main()
