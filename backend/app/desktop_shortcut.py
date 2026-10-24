"""Opt-in Windows desktop shortcut; no startup registration or silent overwrite."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from .data_paths import runtime_root

STATE = runtime_root() / 'desktop-shortcut.json'


def create(target, name, icon, desktop=None):
    target, icon = Path(target).resolve(), Path(icon).resolve()
    if not target.is_file() or not icon.is_file() or any(char in name for char in '\\/:*?"<>|'):
        raise ValueError('快捷方式目标、名称或图标无效')
    env = os.environ.copy()
    env.update(SHION_SHORTCUT_TARGET=str(target), SHION_SHORTCUT_NAME=name,
               SHION_SHORTCUT_ICON=str(icon), SHION_SHORTCUT_DESKTOP=str(desktop or ''))
    script = '''$ErrorActionPreference='Stop'
$desktop = if ($env:SHION_SHORTCUT_DESKTOP) { $env:SHION_SHORTCUT_DESKTOP } else { [Environment]::GetFolderPath('Desktop') }
$path = Join-Path $desktop ($env:SHION_SHORTCUT_NAME + '.lnk')
if (Test-Path -LiteralPath $path) { exit 3 }
$link = (New-Object -ComObject WScript.Shell).CreateShortcut($path)
$link.TargetPath = $env:SHION_SHORTCUT_TARGET
$link.WorkingDirectory = Split-Path -Parent $env:SHION_SHORTCUT_TARGET
$link.IconLocation = $env:SHION_SHORTCUT_ICON + ',0'
$link.Description = '启动应用；关闭启动窗口会停止其管理的服务'
$link.Save()
'''
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
                            env=env, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    if result.returncode == 3:
        return '桌面已有同名快捷方式，未覆盖。'
    if result.returncode:
        raise OSError('无法创建快捷方式，请检查桌面目录的权限。应用仍可正常启动。')
    return '桌面快捷方式已创建。'


def offer(target, name, icon, force=False):
    if os.name != 'nt' or not sys.stdin.isatty():
        return
    if STATE.exists() and not force:
        return
    try:
        answer = input('是否创建桌面快捷方式？[y/N，默认不创建] ').strip().lower()
        if answer in ('y', 'yes'):
            print(create(target, name, icon))
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps({'asked': True, 'accepted': answer in ('y', 'yes')}), encoding='utf-8')
    except (EOFError, KeyboardInterrupt):
        print('\n已跳过快捷方式，继续启动。')
    except (OSError, ValueError) as error:
        print(f'快捷方式未创建：{error}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--target', required=True)
    parser.add_argument('--name', default='Shionarium')
    parser.add_argument('--icon', required=True)
    parser.add_argument('--ask-again', action='store_true')
    args = parser.parse_args()
    offer(args.target, args.name, args.icon, args.ask_again)


if __name__ == '__main__':
    main()
