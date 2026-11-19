"""Windows local runtime: stop only processes created and identified by this launcher."""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import hashlib
import importlib.util
import json
import msvcrt
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request

APP = Path(__file__).resolve().parents[1]
PROJECT = APP.parent
RUNTIME = APP / 'runtime'
ENV_KEYS = ('DB_PATH', 'LLM_MODE', 'OLLAMA_URL', 'OLLAMA_MODEL', 'OLLAMA_NUM_GPU', 'LLM_TIMEOUT',
            'VISION_MODEL_PATH', 'NLP_CORPUS_PATH', 'CORS_ORIGINS', 'API_TIMEOUT_SECONDS',
            'YAMNET_MODEL_PATH', 'YAMNET_LABELS_PATH', 'YAMNET_PYTHON')


def identity(pid):
    """Kernel creation time prevents acting on an unrelated reused PID."""
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x1000, False, int(pid))
    if not handle:
        return None
    try:
        code = wintypes.DWORD()
        if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value != 259:
            return None
        values = [wintypes.FILETIME() for _ in range(4)]
        if not kernel.GetProcessTimes(handle, *(ctypes.byref(v) for v in values)):
            return None
        return str((values[0].dwHighDateTime << 32) | values[0].dwLowDateTime)
    finally:
        kernel.CloseHandle(handle)


def owned(entry):
    return bool(entry and entry.get('created') and identity(entry['pid']) == entry['created'])


def listening(port):
    with socket.socket() as sock:
        sock.settimeout(0.3)
        return sock.connect_ex(('127.0.0.1', port)) == 0


def health(url, api=False):
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(url, timeout=2) as response:
            body = response.read()
            return response.status == 200 and (not api or json.loads(body).get('status') == 'ok')
    except (OSError, ValueError):
        return False


def environment(args):
    env = os.environ.copy()
    dotenv = Path(args.env_file).resolve() if args.env_file else APP / '.env'
    if args.env_file and not dotenv.is_file():
        raise RuntimeError(f'Arquivo .env nao encontrado: {dotenv}')
    if dotenv.is_file():
        from dotenv import dotenv_values
        for key, value in dotenv_values(dotenv, interpolate=False).items():
            if value is not None:
                env.setdefault(key, value)
    defaults = {'DB_PATH': 'data/bairro.sqlite3', 'LLM_MODE': 'extractive',
                'OLLAMA_URL': 'http://127.0.0.1:11434', 'OLLAMA_MODEL': 'gemma3:1b',
                'LLM_TIMEOUT': '90', 'API_TIMEOUT_SECONDS': '100',
                'NLP_CORPUS_PATH': str(APP / 'resources/corpus_texto.jsonl')}
    for key, value in defaults.items():
        env.setdefault(key, value)
    if args.with_models:
        env['LLM_MODE'] = 'ollama'
        env.setdefault('VISION_MODEL_PATH', str(APP / 'modelos/vision/best.onnx'))
    for key in ('DB_PATH', 'VISION_MODEL_PATH', 'NLP_CORPUS_PATH', 'YAMNET_MODEL_PATH', 'YAMNET_LABELS_PATH', 'YAMNET_PYTHON'):
        if env.get(key):
            path = Path(env[key]).expanduser()
            env[key] = str((APP / path).resolve() if not path.is_absolute() else path.resolve())
    if env.get('VISION_MODEL_PATH') and not Path(env['VISION_MODEL_PATH']).is_file():
        raise RuntimeError(f'Modelo de visao inexistente: {env["VISION_MODEL_PATH"]}')
    if not Path(env['NLP_CORPUS_PATH']).is_file():
        raise RuntimeError(f'Corpus inexistente: {env["NLP_CORPUS_PATH"]}')
    env['API_BASE_URL'] = f'http://127.0.0.1:{args.api_port}'
    env.setdefault('CORS_ORIGINS', f'http://localhost:{args.ui_port},http://127.0.0.1:{args.ui_port}')
    env['PYTHONUNBUFFERED'] = '1'
    return env


def save(path, state):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(state, indent=2), encoding='utf-8')
    temp.replace(path)


def configuration_fingerprint(env, executable=None):
    configuration = {k: env.get(k) for k in ENV_KEYS}
    configuration['python_executable'] = os.path.normcase(str(Path(executable or sys.executable).resolve()))
    return hashlib.sha256(json.dumps(configuration, sort_keys=True).encode()).hexdigest()


def terminate(entry):
    if owned(entry):
        os.kill(entry['pid'], 15)
        for _ in range(30):
            if not owned(entry):
                return
            time.sleep(0.1)
        raise RuntimeError(f'Processo {entry["pid"]} ainda ativo.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['start', 'stop', 'status'])
    parser.add_argument('--api-port', type=int, default=8000)
    parser.add_argument('--ui-port', type=int, default=8502)
    parser.add_argument('--with-models', action='store_true')
    parser.add_argument('--env-file')
    args = parser.parse_args()
    if os.name != 'nt':
        raise RuntimeError('Este launcher utiliza identificacao de processos do Windows.')
    if args.api_port == args.ui_port or any(not 1024 <= p <= 65535 for p in (args.api_port, args.ui_port)):
        raise RuntimeError('Escolha duas portas distintas entre 1024 e 65535.')
    RUNTIME.mkdir(exist_ok=True)
    # Concurrent clicks for the same instance must not launch duplicate processes.
    with (RUNTIME / f'processes-{args.api_port}-{args.ui_port}.lock').open('a+b') as lock:
        if lock.tell() == 0:
            lock.write(b'0')
            lock.flush()
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            raise RuntimeError('Outra operacao desta instancia esta em andamento. Tente novamente ao concluir.')
        try:
            run_runtime(args)
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


def run_runtime(args):
    state_path = RUNTIME / f'processes-{args.api_port}-{args.ui_port}.json'
    state = json.loads(state_path.read_text(encoding='utf-8-sig')) if state_path.exists() else {}
    if state and state.get('app_root') != str(APP):
        raise RuntimeError('Registro pertence a outro diretorio; nenhum processo foi alterado.')
    specs = {
        'api': (args.api_port, f'http://127.0.0.1:{args.api_port}/health'),
        'ui': (args.ui_port, f'http://127.0.0.1:{args.ui_port}/_stcore/health'),
    }
    if args.action == 'status':
        print(json.dumps({name: {'port': port, 'listening': listening(port),
              'healthy': health(url, name == 'api'), 'managed': owned(state.get(name)),
              'pid': state.get(name, {}).get('pid'), 'python_executable': state.get('python_executable')}
              for name, (port, url) in specs.items()}, indent=2))
        return
    if args.action == 'stop':
        for name in ('ui', 'api'):
            terminate(state.get(name))
        if state_path.exists():
            state_path.unlink()
        print('Processos registrados encerrados. Servicos externos foram preservados.')
        return
    for module in ('uvicorn', 'fastapi', 'streamlit', 'dotenv'):
        if importlib.util.find_spec(module) is None:
            raise RuntimeError(f'Dependencia ausente: {module}. Instale os requirements do backend e frontend no Python selecionado.')
    env = environment(args)
    fingerprint = configuration_fingerprint(env)
    if state.get('fingerprint') not in (None, fingerprint) and any(owned(state.get(n)) for n in specs):
        raise RuntimeError('Configuracao mudou. Use runtime_stop.ps1 com estas portas e inicie novamente.')
    for name, (port, url) in specs.items():
        if listening(port) and not owned(state.get(name)):
            raise RuntimeError(f'Porta {port} ocupada por processo sem registro deste launcher. Nenhum processo foi parado. Escolha outra porta ou encerre o servico pelo seu terminal original.')
    state.update(app_root=str(APP), fingerprint=fingerprint, mode=env['LLM_MODE'],
                 python_executable=str(Path(sys.executable).resolve()))
    commands = {
        'api': [sys.executable, '-m', 'uvicorn', 'backend.main:app', '--app-dir', str(APP), '--host', '127.0.0.1', '--port', str(args.api_port)],
        'ui': [sys.executable, '-m', 'streamlit', 'run', str(APP / 'frontend/app.py'), '--server.address', '127.0.0.1', '--server.port', str(args.ui_port), '--server.headless', 'true', '--browser.gatherUsageStats', 'false'],
    }
    started = []
    try:
        for name, (port, url) in specs.items():
            if not owned(state.get(name)):
                stamp = time.strftime('%Y%m%d-%H%M%S')
                log = RUNTIME / f'{name}-{port}-{stamp}.log'
                with log.open('ab') as output:
                    process = subprocess.Popen(commands[name], cwd=APP, env=env, stdin=subprocess.DEVNULL,
                                               stdout=output, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
                state[name] = {'pid': process.pid, 'created': identity(process.pid), 'log': str(log)}
                started.append(name)
                save(state_path, state)
            deadline = time.monotonic() + 45
            while not health(url, name == 'api'):
                if not owned(state[name]) or time.monotonic() > deadline:
                    raise RuntimeError(f'{name} nao ficou saudavel. Consulte {state[name].get("log")}')
                time.sleep(0.3)
        print(f'Bairro em Dia: http://127.0.0.1:{args.ui_port} | API: http://127.0.0.1:{args.api_port}/docs | modo: {env["LLM_MODE"]}')
        print(f'Registro: {state_path}')
        if env['LLM_MODE'] == 'ollama':
            print(f'Ollama configurado: {env["OLLAMA_MODEL"]}. Execute a pre-validacao de modelos antes de gravar; health HTTP nao comprova inferencia.')
    except Exception:
        for name in reversed(started):
            terminate(state.get(name))
            state.pop(name, None)
        save(state_path, state)
        raise


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'ERRO: {exc}', file=sys.stderr)
        sys.exit(1)
