"""Exercise real start/reuse/stop and protection of foreign listeners on isolated ports."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import urllib.request

import runtime_manager as runtime


def run():
    ports = (18082, 18582)
    if any(runtime.listening(p) for p in (*ports, 18083, 18583)):
        raise RuntimeError('Portas de teste ocupadas; nada sera interrompido.')
    env = os.environ.copy()
    for key in runtime.ENV_KEYS:
        env.pop(key, None)
    manager = str(Path(__file__).with_name('runtime_manager.py'))
    def call(action, *extra, expect=0, test_ports=ports):
        result = subprocess.run([sys.executable, manager, action, '--api-port', str(test_ports[0]),
                                 '--ui-port', str(test_ports[1]), *extra], env=env, capture_output=True, text=True, timeout=100)
        assert result.returncode == expect, result.stdout + result.stderr
        return result
    runtime.RUNTIME.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='runtime-test-', dir=runtime.RUNTIME) as folder:
        fixture = Path(folder)
        dotenv = fixture / '.env'
        database = fixture / 'env-loaded.sqlite3'
        relative_database = database.relative_to(runtime.APP).as_posix()
        dotenv.write_text(f'LLM_MODE=extractive\nDB_PATH={relative_database}\nAPI_TIMEOUT_SECONDS=37\n', encoding='utf-8')
        try:
            call('start', '--env-file', str(dotenv))
            state_path = runtime.RUNTIME / 'processes-18082-18582.json'
            first = json.loads(state_path.read_text())
            assert Path(first['python_executable']) == Path(sys.executable).resolve(), 'Interpretador nao registrado'
            assert runtime.configuration_fingerprint(env) != runtime.configuration_fingerprint(env, str(fixture / 'other-python.exe'))
            call('start', '--env-file', str(dotenv))
            assert json.loads(state_path.read_text()) == first, 'Reinicio duplicou processos ou alterou registro'
            assert runtime.health('http://127.0.0.1:18082/health', api=True)
            assert runtime.health('http://127.0.0.1:18582/_stcore/health')
            with urllib.request.build_opener(urllib.request.ProxyHandler({})).open('http://127.0.0.1:18082/reports') as response:
                assert response.status == 200
            assert database.exists(), '.env ou caminho relativo nao respeitado'
            changed = call('start', '--env-file', str(dotenv), '--with-models', expect=1)
            assert 'Configuracao mudou' in changed.stderr
            assert runtime.owned(first['api']) and runtime.owned(first['ui'])
            assert not runtime.owned({'pid': os.getpid(), 'created': 'wrong-time'}), 'PID reutilizado aceito'
            call('stop')
            assert not any(runtime.listening(p) for p in ports), 'Stop deixou listener'
            call('stop')
            bad_env = fixture / 'bad.env'
            bad_env.write_text('CORS_ORIGINS=*\n', encoding='utf-8')
            failed = call('start', '--env-file', str(bad_env), expect=1)
            assert 'nao ficou saudavel' in failed.stderr
            assert not any(runtime.listening(p) for p in ports), 'Falha deixou processo iniciado'
            with socket.socket() as foreign:
                foreign.bind(('127.0.0.1', 18083))
                foreign.listen()
                blocked = call('start', expect=1, test_ports=(18083, 18583))
                assert 'Porta 18083 ocupada' in blocked.stderr
                assert runtime.listening(18083) and not runtime.listening(18583)
            print(json.dumps({'result': 'passed', 'checks': ['real_api_and_ui_health', 'same_pids_on_repeat',
                  'dotenv_and_relative_database', 'configuration_change_requires_stop', 'python_identity_in_fingerprint',
                  'reused_pid_rejected', 'stop_and_repeated_stop', 'startup_failure_cleanup', 'foreign_listener_preserved']}, indent=2))
        finally:
            call('stop')


if __name__ == '__main__':
    run()
