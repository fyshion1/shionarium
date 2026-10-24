"""Offline market checks: temporary directories, no model or remote calls."""
import asyncio
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.file_lock import acquire
from app import plugin_state
from app.services import plugin_market as market
from app.routers import plugin_market as router


class MarketTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for target, name, value in [(market, 'JOBS', self.root/'jobs'),
                                    (plugin_state, 'STATE_PATH', self.root/'state.json')]:
            change=patch.object(target,name,value);change.start();self.addCleanup(change.stop)
        change=patch.object(market,'features_root',return_value=self.root/'features')
        change.start();self.addCleanup(change.stop)

    def test_catalog_includes_uninstalled_entries_and_explains_private_tools(self):
        with patch.object(market,'component_ready',return_value=False):
            items=market.catalog()['items']
        self.assertEqual([r['id'] for r in items[:2]],['desktop_pet','qq_bridge'])
        self.assertTrue(all(not r['installed'] for r in items))
        self.assertFalse(next(r for r in items if r['id']=='tools')['available'])
        self.assertTrue(any('ASR' in r['description'] and 'TTS' in r['description'] for r in items))

    def test_unknown_private_unaccepted_and_stale_requests_start_nothing(self):
        for args in [('unknown','1',True),('tools','unpublished',True),('qq_bridge','wrong',True),
                     ('qq_bridge',market.entry('qq_bridge')['revision'],False)]:
            with patch.object(market.threading,'Thread') as thread:
                with self.assertRaises(market.MarketError):market.start(*args)
                thread.assert_not_called()

    def test_existing_directory_is_never_overwritten(self):
        target=self.root/'features/qq-bridge';target.mkdir(parents=True)
        config=target/'config.json';config.write_text('keep')
        with self.assertRaises(market.MarketError):
            market.start('qq_bridge',market.entry('qq_bridge')['revision'],True)
        self.assertEqual(config.read_text(),'keep')
        self.assertFalse(market.active())

    def test_concurrent_install_is_rejected_with_cross_process_lock(self):
        market.JOBS.mkdir()
        with (market.JOBS/'install.lock').open('a+b') as handle:
            self.assertTrue(acquire(handle));self.assertTrue(market.active())
            with self.assertRaises(market.MarketError):
                market.start('qq_bridge',market.entry('qq_bridge')['revision'],True)
        self.assertFalse(market.active())

    def test_success_publishes_only_after_dependencies_and_keeps_disabled(self):
        item=market.entry('qq_bridge');job={'id':'a'*32}
        def fetch(repository, revision, stage, log):
            self.assertEqual(revision, item['revision'])
            (stage/'bridge.py').write_text('# synthetic fixture')
            (stage/'requirements.txt').write_text('')
        def command(args,cwd,log,label,env=None):
            self.assertFalse((self.root/'features/qq-bridge').exists())
        with patch.object(market,'command',side_effect=command), patch.object(market, '_uv', return_value='uv'), \
             patch.object(market.mirror_sources, 'fetch_github_tarball', side_effect=fetch):
            market.install_plugin(item,job,self.root/'log')
        self.assertTrue((self.root/'features/qq-bridge/bridge.py').is_file())
        self.assertFalse(plugin_state.enabled('qq_bridge'))

    def test_failed_download_does_not_publish_partial_plugin(self):
        with patch.object(market.mirror_sources, 'fetch_github_tarball', side_effect=RuntimeError('offline')):
            with self.assertRaises(market.MarketError):market.install_plugin(market.entry('qq_bridge'),{'id':'b'*32},self.root/'log')
        self.assertFalse((self.root/'features/qq-bridge').exists())
        self.assertEqual(list((self.root/'features').iterdir()),[])

    def test_symlink_target_is_rejected(self):
        target=self.root/'features/qq-bridge';target.parent.mkdir()
        with patch.object(Path,'is_symlink',return_value=True):
            with self.assertRaises(market.MarketError):market.install_plugin(market.entry('qq_bridge'),{},self.root/'log')

    def test_dead_owner_marks_interrupted_job_as_failed(self):
        market.save(dict(id='c'*32,status='running',owner_pid=99999999,owner_created=0))
        self.assertEqual(market.read_job('c'*32)['status'],'failed')

    def test_thread_start_failure_is_recorded_and_releases_lock(self):
        with patch.object(market.threading.Thread, 'start', side_effect=RuntimeError('unavailable')):
            with self.assertRaises(RuntimeError):
                market.start('qq_bridge', market.entry('qq_bridge')['revision'], True)
        self.assertFalse(market.active())
        self.assertEqual(market.jobs()[0]['status'], 'failed')

    def test_install_routes_require_local_dashboard_and_explicit_confirmation(self):
        app=FastAPI();app.include_router(router.router,prefix='/api');client=TestClient(app)
        self.assertEqual(client.post('/api/plugin-market/install',json={'id':'qq_bridge','revision':'x'}).status_code,403)
        headers={'X-Exploration-Dashboard':'1'}
        self.assertEqual(client.post('/api/plugin-market/install',headers=headers,json={'id':'qq_bridge','revision':'x'}).status_code,409)
        with patch.object(market,'start',return_value={'id':'d'*32,'status':'running'}) as start:
            response=client.post('/api/plugin-market/install',headers=headers,json={'id':'qq_bridge','revision':'test','accept_code':True})
            self.assertEqual(response.status_code,202);start.assert_called_once_with('qq_bridge','test',True)
        response=client.post('/api/plugin-market/install',headers={**headers,'Origin':'https://untrusted.example'},json={'id':'qq_bridge','revision':'x'})
        self.assertEqual(response.status_code,403)


class LauncherLockTests(unittest.TestCase):
    def test_second_process_reports_locked_without_reading_locked_byte(self):
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'launcher.lock'
            code="from pathlib import Path; from app.file_lock import acquire; import sys; f=Path(sys.argv[1]).open('a+b'); print('acquired' if acquire(f) else 'already-running')"
            with target.open('a+b') as owner:
                self.assertTrue(acquire(owner))
                result=subprocess.run([sys.executable,'-c',code,str(target)],capture_output=True,text=True,timeout=20)
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertEqual(result.stdout.strip(),'already-running')
            result=subprocess.run([sys.executable,'-c',code,str(target)],capture_output=True,text=True,timeout=20)
            self.assertEqual(result.stdout.strip(),'acquired')


if __name__=='__main__':unittest.main()
