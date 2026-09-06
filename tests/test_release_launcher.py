import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.release_launcher import compatible_asset, finalize, fingerprint


class ReleaseLauncherTest(unittest.TestCase):
    def release(self):
        return dict(tag_name='v1.2.73', draft=False, assets=[dict(
            name='ok-gf2-win32-v1.2.73.zip', state='uploaded', digest='sha256:' + 'a' * 64,
        )])

    def test_bootstrap_requires_matching_build_inputs(self):
        self.assertIsNotNone(compatible_asset(self.release(), 'same', baseline_identity='same'))
        self.assertIsNone(compatible_asset(self.release(), 'changed', baseline_identity='same'))

    def test_manifest_rejects_different_configuration_or_digest(self):
        release = self.release()
        manifest = dict(fingerprint='same', asset=release['assets'][0]['name'], sha256='a' * 64)
        self.assertIsNotNone(compatible_asset(release, 'same', manifest))
        self.assertIsNone(compatible_asset(release, 'changed', manifest))
        manifest['sha256'] = 'b' * 64
        self.assertIsNone(compatible_asset(release, 'same', manifest))

    def test_incomplete_draft_or_unverifiable_assets_are_not_reused(self):
        for field, value in [('state', 'new'), ('digest', ''), ('digest', 'sha256:invalid')]:
            with self.subTest(field=field, value=value):
                release = self.release()
                release['assets'][0][field] = value
                self.assertIsNone(compatible_asset(release, 'same', baseline_identity='same'))
        release = self.release()
        release['draft'] = True
        self.assertIsNone(compatible_asset(release, 'same', baseline_identity='same'))

    def test_python_changes_reuse_launcher_but_config_and_icons_invalidate_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'icons').mkdir()
            (root / 'icons/icon.png').write_bytes(b'icon')
            (root / 'pyappify.yml').write_bytes(b'name: app\n')
            original = fingerprint(root)
            (root / 'main.py').write_text('print("new application version")')
            self.assertEqual(original, fingerprint(root))
            (root / 'pyappify.yml').write_bytes(b'name: app\r\n')
            self.assertEqual(original, fingerprint(root))
            (root / 'icons/icon.png').write_bytes(b'new icon')
            self.assertNotEqual(original, fingerprint(root))
            (root / 'icons/icon.png').write_bytes(b'icon')
            (root / 'pyappify.yml').write_bytes(b'name: changed\n')
            self.assertNotEqual(original, fingerprint(root))

    def test_final_manifest_describes_actual_versioned_zip(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'manifest.json'
            source.write_text(json.dumps(dict(fingerprint='same', version='v1.2.3')))
            (root / 'ok-gf2-win32-v1.2.74.zip').write_bytes(b'zip bytes')
            finalize(source, root, 'v1.2.74')
            result = json.loads((root / 'launcher-manifest.json').read_text())
            self.assertEqual('ok-gf2-win32-v1.2.74.zip', result['asset'])
            self.assertEqual(hashlib.sha256(b'zip bytes').hexdigest(), result['sha256'])


if __name__ == '__main__':
    unittest.main()
