import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.services import qq_gateway_setup as setup
from app.services.snowluma import SnowLumaError
from app.routers.qq_bridge import router


class GatewaySetupTests(unittest.TestCase):
    def test_missing_and_old_are_distinct_from_unknown(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(setup, 'folder', return_value=Path(temp)), \
             patch.object(setup, 'qq_versions', return_value=['9.9.30']), \
             patch('app.routers.nest._port_listening', return_value=False):
            result = setup.diagnostics()
            self.assertFalse(result['installed'])
            self.assertTrue(result['old_qq'])
            with patch.object(setup, 'qq_versions', return_value=[]):
                self.assertFalse(setup.diagnostics()['old_qq'])

    def test_only_official_full_release_selected(self):
        def asset(name):
            return {'name': name, 'size': 10, 'browser_download_url': setup.RELEASES + '/download/v1/' + name}
        with patch.object(setup, 'fetch_json', return_value={'tag_name': 'v1', 'assets': [
            asset('SnowLuma-v1-win-x64.zip'), asset('SnowLuma-v1-win-x64-lite.zip')]}):
            self.assertEqual(setup.release()['name'], 'SnowLuma-v1-win-x64.zip')
        with patch.object(setup, 'fetch_json', return_value={'assets': []}):
            with self.assertRaises(SnowLumaError): setup.release()

    def test_install_endpoint_never_downloads_or_writes_gateway(self):
        app = FastAPI(); app.include_router(router, prefix='/api')
        with TestClient(app) as client, patch.object(setup.urllib.request, 'urlopen') as network:
            url = '/api/qq-bridge/setup/install'
            self.assertEqual(client.post(url, json={'version': 'v1', 'consent': True}).status_code, 403)
            result = client.post(url, headers={'X-Exploration-Dashboard': '1'}, json={'version': 'v1', 'consent': True})
            self.assertEqual(result.status_code, 400)
            self.assertIn('自动安装已停用', result.json()['detail'])
            network.assert_not_called()

    def test_password_not_part_of_diagnostics_and_private_reveal(self):
        with patch('app.routers.nest._tail', return_value='token=not-for-display\ninitial password: sample-test-only\n'):
            result = setup.initial_password_notice()
            self.assertIn('sample-test-only', result['notice'])
            self.assertNotIn('token=', result['notice'])

    def test_direct_install_is_blocked_even_with_version(self):
        with patch.object(setup, 'release') as release:
            with self.assertRaisesRegex(SnowLumaError, '§5.4'):
                setup.install('v1')
            release.assert_not_called()
