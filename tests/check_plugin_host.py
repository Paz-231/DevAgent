"""Check the installed plugin through the Codex app-server without model calls."""

import json
from pathlib import Path
from queue import Empty, Queue
import subprocess
import tempfile
from threading import Thread
import time


def check_host():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / '.codex-plugin/plugin.json').read_text())
    expected = {f"devagent:{Path(path).name}" for path in manifest['skills']}
    process = subprocess.Popen(
        ['npx', '--yes', '@openai/codex@0.160.0', 'app-server'],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
    )
    responses = Queue()

    def read_stdout():
        for line in process.stdout:
            responses.put(line)
        responses.put(None)

    reader = Thread(target=read_stdout, daemon=True)
    reader.start()

    def send(message):
        process.stdin.write(json.dumps(message) + '\n')
        process.stdin.flush()

    def receive(request_id):
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            try:
                line = responses.get(timeout=max(0, deadline - time.monotonic()))
            except Empty:
                break
            if line is None:
                raise RuntimeError('Codex app-server stopped before responding')
            response = json.loads(line)
            if response.get('id') == request_id:
                if 'error' in response:
                    raise RuntimeError(response['error'])
                return response['result']
        raise TimeoutError('Codex app-server did not respond within 30 seconds')

    try:
        send({'id': 0, 'method': 'initialize', 'params': {
            'clientInfo': {'name': 'devagent_plugin_check', 'version': '1.0.0'},
        }})
        receive(0)
        send({'method': 'initialized', 'params': {}})
        with tempfile.TemporaryDirectory(prefix='devagent-host-check-') as cwd:
            send({'id': 1, 'method': 'skills/list', 'params': {
                'cwds': [cwd], 'forceReload': True,
            }})
            groups = receive(1)['data']
        skills = [skill for group in groups for skill in group['skills']
                  if skill.get('pluginId') == 'devagent@devagent-marketplace']
        errors = [error for group in groups for error in group.get('errors', [])]
        assert not errors, errors
        assert len(skills) == len(expected), skills
        assert {skill['name'] for skill in skills} == expected, skills
        assert all(skill['enabled'] for skill in skills), skills
        print(json.dumps({'loadedSkills': sorted(expected), 'errors': errors}, indent=2))
    finally:
        process.stdin.close()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        reader.join(timeout=5)
        if not reader.is_alive():
            process.stdout.close()


if __name__ == '__main__':
    check_host()
