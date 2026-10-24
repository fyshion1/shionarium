"""Public path rules and neutral model defaults; never access runtime data."""
import importlib.util
from pathlib import Path
import unittest
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('public_tree', ROOT / 'tools/check_public_tree.py')
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)
release_spec = importlib.util.spec_from_file_location('release_assets', ROOT / 'tools/check_release_assets.py')
release_guard = importlib.util.module_from_spec(release_spec)
release_spec.loader.exec_module(release_guard)


class PublicSourceBoundaryTests(unittest.TestCase):
    def test_private_authoring_and_runtime_paths_are_rejected(self):
        paths = [
            '规划探讨.md', '角色设定.md', '项目坑点总结.md', '项目要求.txt',
            'docs/research/private.md', 'docs/plans/private.md',
            'docs/integrations/qq-gateway-snowluma.md', 'backend/sandbox/personal-docs/private.md',
            'docs/tool-agent-evidence/live.json', 'assets/酒馆角色卡/card.png',
            'evals/memory/model-runs/example/results.json',
            'backend/config/runtime.json', 'backend/data/settings.json',
            'assets/live2d/CubismSamples/Haru/Haru.moc3',
            'assets/models/vrm/AliciaSolid_vrm-0.51.vrm',
            'assets/models/vrm/sample.vrm', 'assets/models/fbx/sample.fbx',
            'frontend/public/vendor/live2dcubismcore.min.js',
        ]
        self.assertEqual(guard.violations(paths), paths)

    def test_source_synthetic_cases_and_public_guides_are_allowed(self):
        self.assertEqual(guard.violations([
            'backend/app/db.py', 'docs/guides/character-packs.md',
            'evals/memory/cases.json', 'evals/memory/tests/test_semantic.py',
            'frontend/src/data/characters.ts', 'assets/LICENSE.md',
        ]), [])

    def test_release_guard_rejects_runtime_and_models_but_allows_framework_js(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ['vendor/live2dcubismcore.min.js', 'assets/model.moc3',
                         'assets/AliciaSolid_vrm-0.51.vrm', 'assets/CubismSamples/Haru/texture.png',
                         'voice-capture.js', 'assets/index.js']:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('fixture', encoding='utf-8')
            errors = release_guard.violations(root)
            self.assertEqual(len(errors), 4)
            self.assertNotIn('voice-capture.js', errors)
            self.assertNotIn('assets/index.js', errors)

    def test_no_author_provider_or_model_is_used_as_a_default(self):
        from app.config import Settings
        with patch.dict('os.environ', {}, clear=True):
            settings = Settings(_env_file=None)
        self.assertEqual(settings.model_base_url, '')
        self.assertEqual(settings.model_api_key, '')
        self.assertEqual(settings.model_chat, '')
        self.assertEqual(settings.model_vision, '')


if __name__ == '__main__':
    unittest.main()
