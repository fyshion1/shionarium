"""Explicit local dashboard onboarding. Never exposed as a model tool."""
import json
import os
import re
import urllib.request
from pathlib import Path

from .snowluma import SnowLumaError

RELEASES = 'https://github.com/SnowLuma/SnowLuma/releases'


def folder():
    from ..routers.nest import _gateway_spec
    return Path(_gateway_spec('qq_bridge')['folder'])


def qq_versions():
    """Read running QQ's adjacent manifest; unknown is not evidence of old QQ."""
    if os.name != 'nt':
        return []
    import psutil
    result = set()
    for proc in psutil.process_iter(['name', 'exe']):
        if str(proc.info.get('name') or '').lower() != 'qq.exe':
            continue
        try:
            root = Path(proc.info['exe']).parent
            for p in [root / 'resources/app/package.json', root / 'resources/app/app_launcher/qq_package.json']:
                if p.is_file():
                    value = str(json.loads(p.read_text(encoding='utf-8-sig')).get('version') or '')
                    if re.fullmatch(r'\d+(?:\.\d+){2,4}(?:-\d+)?', value):
                        result.add(value)
        except (OSError, ValueError, TypeError):
            pass
    return sorted(result)


def diagnostics():
    from ..routers.nest import _port_listening, _setting
    target = folder()
    installed = (target / 'node.exe').is_file() and (target / 'index.mjs').is_file()
    versions = qq_versions()
    old = [v for v in versions if tuple(map(int, re.findall(r'\d+', v)[:3])) < (9, 9, 33)]
    return {'installed': installed, 'folder': str(target), 'versions': versions,
            'old_qq': bool(old), 'webui_online': _port_listening(int(_setting('qq_bridge', 'gateway.webui_port', 5099))),
            'releases_url': RELEASES, 'install_supported': False,
            'message': '检测到较旧 QQ，请按所选 SnowLuma 发行说明升级匹配版本；升级后重启 QQ 和网关。' if old else
            'QQ 版本需与 SnowLuma 发行说明匹配；未检测到版本不代表兼容。若一直 connecting，请检查 QQ 登录、加载状态和网关日志。',
            'password_hint': '首次登录密码请在 SnowLuma 启动日志中查看；不同发行版可能不同。登录后按网关提示修改，再将新密码填入下方「网关网页密码」。'}


def initial_password_notice():
    from ..routers.nest import _log_path, _tail
    # Explicit local reveal only; never include this in poll responses or tool receipts.
    text = _tail(_log_path('qq_bridge-gateway'), 1000)
    lines = [line for line in text.splitlines() if re.search(r'初始密码|initial password|default password|默认密码', line, re.I)]
    return {'notice': '\n'.join(lines[-4:]) or '未在小窝启动日志中找到初始密码。请查看 SnowLuma 自己的启动窗口；若已经改过，请使用你修改后的密码。'}


def fetch_json(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'xiaotangren-qq-setup', 'Accept': 'application/vnd.github+json'})
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.load(response)


def release():
    data = fetch_json('https://api.github.com/repos/SnowLuma/SnowLuma/releases/latest')
    assets = [a for a in data.get('assets', []) if re.search(r'win(?:dows)?[-_]x64', a.get('name', ''), re.I)
              and a['name'].endswith('.zip') and 'lite' not in a['name'].lower()]
    if len(assets) != 1:
        raise SnowLumaError('未找到唯一的 Windows x64 完整版，请从官方 Releases 手动安装后填写安装目录。')
    asset = assets[0]
    url = asset['browser_download_url']
    if not url.startswith(RELEASES + '/download/') or not 0 < int(asset.get('size', 0)) <= 600 * 1024 * 1024:
        raise SnowLumaError('发行包地址或大小不符合安装要求')
    return {'version': data['tag_name'], 'name': asset['name'], 'url': url, 'size': asset['size'],
            'notes': str(data.get('body') or '')[:16000]}



def install(version):
    raise SnowLumaError('自动安装已停用：SnowLuma EULA §5.4 要求自动部署事先取得书面授权。请从官方 Releases 阅读协议后手动安装，再填写网关目录。')
