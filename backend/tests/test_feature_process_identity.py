"""Offline process identity and lifecycle regressions; no real plugin launch."""
import asyncio
import unittest
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import Mock, patch
from app.routers import nest
from fastapi import HTTPException


class FeatureProcessTests(unittest.TestCase):
    def setUp(self):
        self.row = {'pid': 12345, 'command': 'run', 'started_at': '2026-10-24 12:00:00', 'stopped_at': ''}
        self.proc = Mock(pid=12345)
        self.proc.cmdline.return_value = ['python.exe', '-m', 'qqbridge', 'run']
        self.proc.create_time.return_value = datetime(2026, 10, 24, 12, tzinfo=timezone.utc).timestamp()

    def identify(self):
        with patch('psutil.Process', return_value=self.proc), patch.object(nest, 'runner_of', return_value={'module': 'qqbridge'}):
            return nest._feature_process('qq_bridge', self.row)

    def test_cwd_is_not_required_for_interpreter_shims(self):
        self.proc.cwd.side_effect = PermissionError('unavailable cwd')
        self.assertIs(self.identify(), self.proc)
        self.proc.cwd.assert_not_called()

    def test_reused_pid_and_module_substrings_are_rejected(self):
        self.proc.create_time.return_value += 60
        self.assertIsNone(self.identify())
        self.proc.create_time.return_value -= 60
        self.proc.cmdline.return_value = ['python', 'other.py', 'qqbridge', 'run']
        self.assertIsNone(self.identify())

    def test_older_live_record_still_prevents_duplicate_start(self):
        with patch.object(nest.db, 'active_feature_runs', return_value=[{'pid': 2}, self.row]), patch.object(nest, '_feature_process', side_effect=[None, self.proc]):
            self.assertEqual(nest._running_pid('qq_bridge'), 12345)

    def test_start_refuses_an_existing_verified_process(self):
        with patch('app.services.qq_basic_settings.require_ready'), patch.object(nest, '_runner', return_value={'runner': {}}), patch.object(nest, '_build_command', return_value=([], {})), patch.object(nest.db, 'latest_feature_run', return_value=self.row), patch.object(nest, '_running_pid', return_value=12345), patch.object(nest.subprocess, 'Popen') as spawn:
            with self.assertRaises(HTTPException) as error:
                asyncio.run(nest.run_feature('qq_bridge', nest.RunIn(command='run')))
            self.assertEqual(error.exception.status_code, 409)
            spawn.assert_not_called()

    def test_stop_includes_interpreter_child(self):
        import psutil
        with tempfile.TemporaryDirectory() as folder:
            marker = Path(folder) / 'child.pid'
            code = ("import subprocess,sys,time; from pathlib import Path; "
                    "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
                    "Path(sys.argv[1]).write_text(str(p.pid)); time.sleep(60)")
            proc = subprocess.Popen([sys.executable, '-c', code, str(marker)], creationflags=nest._CREATE_NEW_GROUP)
            child = None
            try:
                deadline = time.monotonic() + 10
                while not marker.exists() and time.monotonic() < deadline:
                    time.sleep(.05)
                self.assertTrue(marker.exists())
                child = psutil.Process(int(marker.read_text()))
                nest._stop_one(proc, grace=.1)
                self.assertIsNotNone(proc.poll())
                self.assertFalse(child.is_running())
            finally:
                if child is not None and child.is_running():
                    child.kill()
                if proc.poll() is None:
                    proc.kill()
                proc.wait(timeout=5)

    def test_stop_failure_retains_records_for_retry(self):
        self.proc.children.return_value = []
        self.proc.is_running.return_value = True
        with patch.object(nest.db, 'active_feature_runs', return_value=[self.row]), patch.object(nest, '_feature_process', return_value=self.proc), patch.object(nest, '_stop_tree'), patch.object(nest.db, 'stop_feature_runs') as stopped, patch.dict(nest._procs, {}, clear=True):
            result = asyncio.run(nest.stop_feature('qq_bridge'))
        self.assertFalse(result['stopped'])
        stopped.assert_not_called()
