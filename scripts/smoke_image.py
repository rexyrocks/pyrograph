"""Build and smoke-test the exact Dockerfile; requires a running Docker daemon."""
import json
import re
import shutil
import subprocess
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


def main():
    if shutil.which('docker') is None:
        raise SystemExit('BLOCKED: Docker is not installed; image smoke test has not run.')
    subprocess.run(['docker', 'info'], check=True, stdout=subprocess.DEVNULL)
    subprocess.run(['docker', 'build', '-t', 'pyrograph:demo-audit', '.'], check=True)
    key = 'image-smoke-only-key-00000000000000000'
    container = subprocess.check_output([
        'docker', 'run', '-d', '--rm', '-p', '127.0.0.1::8080',
        '-e', f'HEATSHIELD_API_KEY={key}', '-e', 'HEATSHIELD_ALERT_PROVIDER=demo',
        'pyrograph:demo-audit',
    ], text=True).strip()
    if not re.fullmatch(r'[a-f0-9]{64}', container):
        raise RuntimeError('Unexpected container identifier')
    try:
        address = subprocess.check_output(['docker', 'port', container, '8080/tcp'], text=True).strip()
        base = f'http://{address}'
        def get(path, authorized=True):
            return json.load(urlopen(Request(base + path, headers={'X-API-Key': key} if authorized else {}), timeout=5))
        for attempt in range(60):
            try:
                get('/health')
                break
            except (URLError, TimeoutError):
                if attempt == 59:
                    raise
                time.sleep(1)
        wards = get('/demographics/wards')
        assert wards['count'] == 5
        assert wards['suitable_for_operational_use'] is False
        try:
            get('/demographics/wards', authorized=False)
            raise AssertionError('Missing credentials unexpectedly accepted')
        except HTTPError as error:
            assert error.code == 401
        print(json.dumps({'image': 'pyrograph:demo-audit', 'health': 'pass', 'demographics': 'pass', 'authentication': 'pass'}))
    finally:
        subprocess.run(['docker', 'rm', '-f', container], check=True)


if __name__ == '__main__':
    main()
