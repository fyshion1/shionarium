"""Shortcut preferences never write the user's real desktop during tests."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from app import desktop_shortcut as shortcut


class ShortcutTests(unittest.TestCase):
    def test_first_prompt_defaults_no_and_is_not_repeated(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(shortcut,'STATE',Path(folder)/'state.json'),\
             patch.object(shortcut.os,'name','nt'),patch.object(shortcut.sys.stdin,'isatty',return_value=True),\
             patch('builtins.input',return_value='') as question,patch.object(shortcut,'create') as create:
            shortcut.offer('target','name','icon');shortcut.offer('target','name','icon')
            question.assert_called_once();create.assert_not_called()

    def test_yes_creates_selected_brand_shortcut(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(shortcut,'STATE',Path(folder)/'state.json'),\
             patch.object(shortcut.os,'name','nt'),patch.object(shortcut.sys.stdin,'isatty',return_value=True),\
             patch('builtins.input',return_value='y'),patch.object(shortcut,'create',return_value='created') as create:
            shortcut.offer('target','name','icon');create.assert_called_once_with('target','name','icon')

    def test_noninteractive_launch_never_prompts(self):
        with patch.object(shortcut.sys.stdin,'isatty',return_value=False),patch('builtins.input') as question:
            shortcut.offer('target','name','icon');question.assert_not_called()
