import copy
import hashlib
import io
import json
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from app.routers.appearance_packs import router
from app.services import appearance_packs as packs

EXAMPLE = Path(__file__).resolve().parents[2] / 'examples/appearance-packs/paper-ink/theme.json'


def archive(manifest=None, extras=None):
    content = io.BytesIO()
    with zipfile.ZipFile(content, 'w', zipfile.ZIP_DEFLATED) as output:
        output.writestr('theme.json', json.dumps(manifest or json.loads(EXAMPLE.read_text(encoding='utf-8'))))
        for name, value in (extras or {}).items():
            output.writestr(name, value)
    return content.getvalue()


class AppearancePackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.features = self.root / 'plugins'
        self.features.mkdir()
        self.addCleanup(patch.stopall)
        patch.object(packs, 'runtime_root', return_value=self.root / 'data').start()
        patch.object(packs, 'features_root', return_value=self.features).start()
        self.manifest = json.loads(EXAMPLE.read_text(encoding='utf-8'))

    def install(self, manifest=None, extras=None):
        preview = packs.stage(archive(manifest, extras))
        packs.install(preview['token'])
        return preview

    def test_preview_is_not_install_and_remove_retains_backup(self):
        preview = packs.stage(archive())
        self.assertEqual(packs.catalog()[0]['items'], [])
        packs.install(preview['token'])
        item = packs.catalog()[0]['items'][0]
        self.assertEqual(item['id'], 'paper-ink')
        self.assertEqual(item['source'], 'imported')
        with self.assertRaises(packs.PackError):
            packs.install(preview['token'])
        with self.assertRaises(packs.PackError):
            packs.stage(archive())
        packs.uninstall('paper-ink')
        self.assertEqual(packs.catalog()[0]['items'], [])
        backups = list((packs.root() / '.removed').iterdir())
        self.assertTrue((backups[0] / 'theme.json').is_file())
        self.assertFalse((self.root / 'data' / 'plugin-state.json').exists())

    def test_arbitrary_plugin_folder_is_discovered_without_python_or_build(self):
        folder = self.features / 'a-friends-own-skin'
        folder.mkdir()
        (folder / 'theme.json').write_text(json.dumps(self.manifest), encoding='utf-8')
        data = packs.catalog()[0]
        self.assertEqual(data['errors'], [])
        self.assertEqual(data['items'][0]['source'], 'plugin')
        with self.assertRaises(packs.PackError):
            packs.uninstall('paper-ink')
        with patch('app.plugin_state.enabled', return_value=False):
            self.assertEqual(packs.catalog()[0]['items'], [])

    def test_image_hash_type_and_declared_resource_boundary(self):
        image = io.BytesIO()
        Image.new('RGB', (2, 2), '#f4f0e8').save(image, 'PNG')
        name = 'assets/background.png'
        self.manifest['background_file'] = name
        self.manifest['assets'] = {name: hashlib.sha256(image.getvalue()).hexdigest()}
        self.install(self.manifest, {name: image.getvalue()})
        self.assertEqual(packs.asset_file('paper-ink', 'background.png').read_bytes(), image.getvalue())
        for filename in ['theme.json', '../theme.json', 'missing.png']:
            with self.subTest(filename=filename), self.assertRaises(packs.PackError):
                packs.asset_file('paper-ink', filename)
        (packs.root() / 'paper-ink' / name).write_bytes(b'corrupt')
        self.assertEqual(packs.catalog()[0]['items'], [])
        self.assertTrue(packs.catalog()[0]['errors'])

    def test_rejects_css_remote_assets_unknown_versions_and_invalid_tokens(self):
        mutations = [
            ('format_version', 2), ('format_version', True), ('radius', 100),
            ('font_file', 'https://example.invalid/font.woff2'),
            ('background_opacity', 0.9), ('script', 'alert(1)'),
            ('id', '../outside'), ('name', '   '),
        ]
        for field, value in mutations:
            manifest = copy.deepcopy(self.manifest)
            manifest[field] = value
            with self.subTest(field=field), self.assertRaises(packs.PackError):
                packs.parse(archive(manifest))
        self.manifest['colors']['light']['accent'] = 'red; background:url(https://example.invalid)'
        with self.assertRaises(packs.PackError):
            packs.parse(archive(self.manifest))

    def test_rejects_undeclared_files_traversal_symlinks_and_duplicate_paths(self):
        for name in ['style.css', 'run.js', '../outside.txt', '/absolute.png', 'assets\\back.png', 'assets/unused.png']:
            with self.subTest(name=name), self.assertRaises(packs.PackError):
                packs.parse(archive(extras={name: b'payload'}))
        content = io.BytesIO(archive())
        with zipfile.ZipFile(content, 'a') as output:
            link = zipfile.ZipInfo('assets/link.png')
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            output.writestr(link, '../outside')
        with self.assertRaises(packs.PackError):
            packs.parse(content.getvalue())
        with self.assertRaises(packs.PackError):
            packs.parse(archive(extras={'THEME.JSON': b'{}'}))

    def test_limits_and_preview_expiry(self):
        with patch.object(packs, 'MAX_EXPANDED', 10), self.assertRaises(packs.PackError):
            packs.parse(archive())
        preview = packs.stage(archive())
        with patch.object(packs.time, 'time', return_value=packs.time.time() + packs.PREVIEW_TTL + 1):
            with self.assertRaises(packs.PackError):
                packs.install(preview['token'])

    def test_http_access_confirmation_schema_and_resource_allowlist(self):
        app = FastAPI()
        app.include_router(router, prefix='/api')
        headers = {'X-Exploration-Dashboard': '1'}
        with TestClient(app) as client:
            self.assertEqual(client.get('/api/appearance-packs').status_code, 403)
            self.assertEqual(client.post('/api/appearance-packs/preview', files={'file': ('pack.zip', archive())}).status_code, 403)
            preview = client.post('/api/appearance-packs/preview', headers=headers, files={'file': ('pack.zip', archive())})
            self.assertEqual(preview.status_code, 200, preview.text)
            token = preview.json()['token']
            self.assertEqual(client.get('/api/appearance-packs', headers=headers).json()['items'], [])
            self.assertEqual(client.post('/api/appearance-packs/install', json={'token': token}).status_code, 403)
            self.assertEqual(client.post('/api/appearance-packs/install', headers=headers, json={'token': token}).status_code, 200)
            self.assertEqual(client.get('/api/appearance-packs/schema', headers=headers).json(), packs.Manifest.model_json_schema())
            self.assertEqual(client.get('/api/appearance-packs/paper-ink/assets/theme.json').status_code, 404)
            self.assertEqual(client.delete('/api/appearance-packs/paper-ink', headers=headers).status_code, 200)
            image = io.BytesIO()
            Image.new('RGB', (2, 2), '#faf7f1').save(image, 'PNG')
            self.manifest['background_file'] = 'assets/bg.png'
            self.manifest['assets'] = {'assets/bg.png': hashlib.sha256(image.getvalue()).hexdigest()}
            self.install(self.manifest, {'assets/bg.png': image.getvalue()})
            resource = client.get('/api/appearance-packs/paper-ink/assets/bg.png')
            self.assertEqual(resource.content, image.getvalue())
            self.assertEqual(resource.headers['content-type'], 'image/png')
            self.assertEqual(resource.headers['x-content-type-options'], 'nosniff')
            self.assertEqual(client.get('/api/appearance-packs/paper-ink/assets/LICENSE.txt').status_code, 404)

    def test_published_schema_matches_runtime(self):
        schema = EXAMPLE.parents[2] / '../docs/schemas/appearance-pack-v1.schema.json'
        self.assertEqual(json.loads(schema.read_text(encoding='utf-8')), packs.Manifest.model_json_schema())


if __name__ == '__main__':
    unittest.main()
