"""Offline source download, extraction and mirror environment checks."""
import io
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from app.services import mirror_sources as sources


class MirrorTests(unittest.TestCase):
    def archive(self, root, names):
        target = root / 'source.tar.gz'
        with tarfile.open(target, 'w:gz') as archive:
            for name in names:
                member = tarfile.TarInfo(name)
                data = b'fixture'
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))
        return target

    def test_official_source_is_first_and_empty_override_disables_mirrors(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertTrue(sources.github_tarball_urls('owner/repo', 'a'*40)[0].startswith(sources.CODELOAD))
        with patch.dict(os.environ, {'SHIONARIUM_GH_MIRROR': ''}):
            self.assertEqual(len(sources.github_tarball_urls('owner/repo', 'a'*40)), 1)
        with self.assertRaises(ValueError):
            sources.github_tarball_urls('../repo', 'main')

    def test_safe_files_extract_but_unsafe_paths_are_rejected(self):
        for name in ['root/../escape', '/root/escape', 'root/C:/escape', 'root/file:stream', '../escape']:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                with self.assertRaises(ValueError):
                    sources._extract(self.archive(root, [name]), root/'out')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            sources._extract(self.archive(root, ['repo-sha/sub/code.py']), root/'out')
            self.assertEqual((root/'out/sub/code.py').read_bytes(), b'fixture')

    def test_existing_destination_is_not_cleared(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)
            (target/'keep').write_text('keep')
            with self.assertRaises(ValueError):
                sources.fetch_github_tarball('owner/repo','a'*40,target)
            self.assertEqual((target/'keep').read_text(), 'keep')

    def test_fallback_clears_partial_files_and_does_not_publish_them(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = root/'out'
            target.mkdir()
            def extract(archive, dest):
                if not extract.failed:
                    extract.failed = True
                    (dest/'partial').write_text('partial')
                    raise ValueError('truncated')
                self.assertFalse((dest/'partial').exists())
                (dest/'ready').write_text('ready')
            extract.failed = False
            with patch.object(sources,'github_tarball_urls',return_value=['official','fallback']), patch.object(sources,'_download'), patch.object(sources,'_extract',side_effect=extract):
                self.assertEqual(sources.fetch_github_tarball('owner/repo','a'*40,target),'fallback')

    def test_voice_model_download_receives_hf_mirror_without_global_mutation(self):
        with patch.dict(os.environ, {'HF_ENDPOINT':'https://example.invalid'}, clear=True):
            env = sources.install_env()
            self.assertEqual(env['VOICE_MODEL_MIRROR'], 'https://example.invalid')
            self.assertNotIn('VOICE_MODEL_MIRROR', os.environ)
