"""Select a compatible, checksum-verified launcher from this fork's releases."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import urlparse
from urllib.request import Request, urlopen

PYAPPIFY_VERSION = 'v1.2.3'
# Increment this when changing how the binary itself is built, not NSIS compression.
BINARY_RECIPE = 'pyappify-action-c5cc8fe5c9bd5c732969018694a2645474c48b7e'
BASELINE_TAG = 'v1.2.73'
BASELINE_COMMIT = '6f2141db1d7ba1f32283da9b2df6481420e51999'


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args])


def fingerprint(root, ref=None):
    if ref:
        files = git(root, 'ls-tree', '-r', '--name-only', ref, '--', 'icons').decode().splitlines()
    else:
        files = [p.relative_to(root).as_posix() for p in (root / 'icons').rglob('*') if p.is_file()]
    inputs = {}
    for name in sorted(['pyappify.yml', *files]):
        data = git(root, 'show', f'{ref}:{name}') if ref else (root / name).read_bytes()
        if name.endswith('.yml'):
            data = data.replace(b'\r\n', b'\n')
        inputs[name] = hashlib.sha256(data).hexdigest()
    identity = dict(version=PYAPPIFY_VERSION, recipe=BINARY_RECIPE, target='win32-x64', inputs=inputs)
    return hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()


def fetch_json(url):
    headers = {'User-Agent': 'ok-gf2-release'}
    if urlparse(url).netloc == 'api.github.com' and os.environ.get('GITHUB_TOKEN'):
        headers['Authorization'] = 'Bearer ' + os.environ['GITHUB_TOKEN']
    with urlopen(Request(url, headers=headers), timeout=60) as response:
        return json.load(response)


def compatible_asset(release, identity, manifest=None, baseline_identity=None):
    if release.get('draft'):
        return None
    if manifest is not None:
        if manifest.get('fingerprint') != identity:
            return None
        asset_name = manifest.get('asset')
        expected = manifest.get('sha256')
    elif release['tag_name'] == BASELINE_TAG and baseline_identity == identity:
        asset_name = f'ok-gf2-win32-{BASELINE_TAG}.zip'
        expected = None
    else:
        return None
    for asset in release.get('assets', []):
        digest = asset.get('digest', '')
        if asset['name'] == asset_name and asset.get('state') == 'uploaded':
            if not re.fullmatch(r'sha256:[a-f0-9]{64}', digest):
                return None
            if expected is not None and expected != digest[7:]:
                return None
            return asset
    return None


def prepare(root, output):
    identity = fingerprint(root)
    # The initial release predates manifests. Trust only its known source commit.
    baseline_identity = None
    try:
        baseline_ref = git(root, 'rev-parse', f'refs/tags/{BASELINE_TAG}^{{commit}}').decode().strip()
        if (baseline_ref == BASELINE_COMMIT and PYAPPIFY_VERSION == 'v1.2.3'
                and BINARY_RECIPE == 'pyappify-action-c5cc8fe5c9bd5c732969018694a2645474c48b7e'):
            baseline_identity = fingerprint(root, BASELINE_COMMIT)
    except subprocess.CalledProcessError:
        pass
    repository = os.environ['GITHUB_REPOSITORY']
    releases = fetch_json(f'https://api.github.com/repos/{repository}/releases?per_page=30')
    outputs = {'reuse_url': '', 'reuse_asset': '', 'reuse_sha256': '', 'version': PYAPPIFY_VERSION}
    for release in releases:
        manifests = [a for a in release.get('assets', []) if a['name'] == 'launcher-manifest.json']
        manifest = fetch_json(manifests[0]['browser_download_url']) if manifests else None
        asset = compatible_asset(release, identity, manifest, baseline_identity)
        if asset:
            outputs.update(reuse_url=release['url'], reuse_asset=asset['name'], reuse_sha256=asset['digest'][7:])
            print(f"Reusing compatible launcher from {release['tag_name']}: {asset['name']}")
            break
    else:
        print('No compatible launcher release found; compiling a new launcher.')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({'fingerprint': identity, 'version': PYAPPIFY_VERSION}, indent=2), encoding='utf-8')
    with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as handle:
        for key, value in outputs.items():
            handle.write(f'{key}={value}\n')


def finalize(output, dist, version):
    manifest = json.loads(output.read_text(encoding='utf-8'))
    asset = dist / f'ok-gf2-win32-{version}.zip'
    manifest.update(asset=asset.name, sha256=hashlib.sha256(asset.read_bytes()).hexdigest())
    (dist / 'launcher-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['prepare', 'finalize'])
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = root / '.release/launcher-manifest.json'
    if args.command == 'prepare':
        prepare(root, output)
    else:
        finalize(output, root / 'pyappify_dist', os.environ['GITHUB_REF_NAME'])
