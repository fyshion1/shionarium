"""下载源兜底：GitHub 源码走 codeload tar 包，npm / PyPI / HuggingFace 走国内镜像。

为什么需要它
------------
插件市场原来用 `git fetch https://github.com/...` 拉源码。在国内网络下
`github.com` 的 git 协议经常被重置（浏览器能打开、`git fetch` 直接
`Recv failure: Connection was reset`），于是「点安装 → 一直转圈 → 失败」。
实测 `codeload.github.com`（GitHub 自己的 tarball 域名）是可用的，
所以源码改成下载 tar.gz，不再依赖 git，也不再依赖 github.com 的 git 端口。

另外三类依赖各有各的墙：
- npm 官方源慢 → registry.npmmirror.com
- Electron 二进制在 GitHub Releases → npmmirror 的 electron 镜像
- PyPI 慢 → 清华 / 阿里
- HuggingFace 模型（huggingface.co 直连超时）→ hf-mirror.com

设计取舍
--------
- **官方源优先**：先直连 codeload，失败才按顺序降级到镜像；
- **只影响本机安装**：通过子进程 env 注入，不改用户的全局 npm/pip 配置；
- **全部可覆盖**：环境变量固定镜像，或设成空值强制只用官方源。
"""
from __future__ import annotations

import os
import re
from pathlib import Path
import shutil
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import PurePosixPath

CODELOAD = 'https://codeload.github.com'

# 镜像可以往这里加；顺序即降级顺序。空串 = 官方直连。
DEFAULT_GH_MIRRORS = ('', 'https://gh-proxy.com/', 'https://ghfast.top/')

NPM_REGISTRY = 'https://registry.npmmirror.com'
PYPI_INDEX = 'https://pypi.tuna.tsinghua.edu.cn/simple'
ELECTRON_MIRROR = 'https://npmmirror.com/mirrors/electron/'
HF_ENDPOINT = 'https://hf-mirror.com'

_UA = {'User-Agent': 'Shionarium-plugin-market/1.0'}


def _env(name: str, default: str) -> str:
    value = os.environ.get(name)
    return default if value is None else value.strip()


def github_tarball_urls(repository: str, revision: str) -> list[str]:
    """按「官方 → 镜像」的顺序给出候选下载地址。

    `SHIONARIUM_GH_MIRROR` 可指定单个前缀（如 `https://gh-proxy.com/`），
    设为空字符串则只用官方直连。
    """
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository) or not re.fullmatch(r'[a-f0-9]{40}', revision):
        raise ValueError('下载只接受明确的 GitHub 仓库和完整提交哈希')
    fixed = os.environ.get('SHIONARIUM_GH_MIRROR')
    prefixes = [fixed] if fixed is not None else list(DEFAULT_GH_MIRRORS)
    base = f'{CODELOAD}/{repository}/tar.gz/{revision}'
    urls = []
    for prefix in prefixes:
        prefix = (prefix or '').strip().rstrip('/')
        urls.append(f'{prefix}/{base}' if prefix else base)
    return urls


def npm_env() -> dict:
    """npm / Electron 安装时的镜像环境（只作用于子进程）。"""
    return {
        'npm_config_registry': _env('SHIONARIUM_NPM_REGISTRY', NPM_REGISTRY),
        'ELECTRON_MIRROR': _env('ELECTRON_MIRROR', ELECTRON_MIRROR),
        'ELECTRON_BUILDER_BINARIES_MIRROR': _env(
            'ELECTRON_BUILDER_BINARIES_MIRROR',
            'https://npmmirror.com/mirrors/electron-builder-binaries/'),
        'npm_config_disturl': _env('SHIONARIUM_NODE_DISTURL', 'https://npmmirror.com/mirrors/node/'),
        'SASS_BINARY_SITE': _env('SASS_BINARY_SITE', 'https://npmmirror.com/mirrors/node-sass/'),
        'npm_config_fetch_timeout': '120000',
    }


def pip_env() -> dict:
    """uv / pip 安装时的镜像环境（只作用于子进程）。"""
    index = _env('SHIONARIUM_PYPI_INDEX', PYPI_INDEX)
    return {
        'UV_DEFAULT_INDEX': index,
        'PIP_INDEX_URL': index,
        'UV_HTTP_TIMEOUT': '180',
    }


def hf_env() -> dict:
    """HuggingFace 模型下载的镜像环境。"""
    endpoint = (_env('HF_ENDPOINT', '') or _env('HF_MIRROR', '') or HF_ENDPOINT)
    return {
        'HF_ENDPOINT': endpoint,
        'HF_MIRROR': endpoint,
        'HUGGINGFACE_HUB_ENDPOINT': endpoint,
        'VOICE_MODEL_MIRROR': _env('VOICE_MODEL_MIRROR', endpoint),
    }


def install_env() -> dict:
    """可选组件（install-features.py）一次拿全。"""
    return {**pip_env(), **hf_env()}


def _say(log: Path | None, text: str) -> None:
    if log is None:
        return
    try:
        with log.open('a', encoding='utf-8') as handle:
            handle.write(text + '\n')
    except OSError:
        pass


def _download(url: str, target: Path, timeout: int = 120, log: Path | None = None) -> None:
    request = urllib.request.Request(url, headers=_UA)
    _say(log, f'→ 下载 {url}')
    with urllib.request.urlopen(request, timeout=timeout) as response, target.open('wb') as output:
        expected = response.headers.get('Content-Length')
        size = 0
        deadline = time.monotonic() + timeout
        while chunk := response.read(256 * 1024):
            size += len(chunk)
            if size > 128 * 1024 * 1024 or time.monotonic() > deadline:
                raise ValueError('源码下载超过大小或时间限制')
            output.write(chunk)
    size = target.stat().st_size
    if size == 0:
        raise ValueError('下载内容为空')
    if expected is not None and int(expected) != size:
        raise ValueError(f'下载不完整（{size}/{expected} 字节）')
    _say(log, f'  完成 {size} 字节')


def _extract(tar_path: Path, dest: Path) -> None:
    """Extract a single GitHub root, rejecting traversal and Windows ADS paths."""
    root = None
    expanded = 0
    count = 0
    with tarfile.open(tar_path, 'r:gz') as archive:
        for member in archive:
            count += 1
            name = member.name.replace('\\', '/')
            path = PurePosixPath(name)
            parts = path.parts
            if (path.is_absolute() or not parts or '..' in parts
                    or any(':' in part or part.endswith((' ', '.')) for part in parts)):
                raise ValueError('压缩包内含可疑路径')
            if root is None:
                root = parts[0]
            if parts[0] != root:
                raise ValueError('源码压缩包必须只有一个顶层目录')
            expanded += member.size
            if count > 20000 or expanded > 512 * 1024 * 1024:
                raise ValueError('源码解压超过大小或文件数量限制')
            if len(parts) == 1:
                continue
            target = dest.joinpath(*parts[1:])
            if not target.resolve().is_relative_to(dest.resolve()):
                raise ValueError('源码路径超出安装目录')
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                target.parent.mkdir(parents=True, exist_ok=True)
                source = archive.extractfile(member)
                if source is not None:
                    with source, target.open('wb') as output:
                        shutil.copyfileobj(source, output)
                    target.chmod(member.mode & 0o777)
            # Symlinks, hardlinks, devices and FIFOs are never installed.


def fetch_github_tarball(repository: str, revision: str, dest: Path,
                         log: Path | None = None, timeout: int = 120) -> str:
    """把某个固定 commit 的源码取到 `dest`（目录需已存在且为空）。

    依次尝试官方与镜像；全部失败时抛出带各源错误摘要的 RuntimeError。
    返回最终成功的 URL。
    """
    dest.mkdir(parents=True, exist_ok=True)
    if any(dest.iterdir()):
        raise ValueError('源码下载目标必须为空，不会清除已有文件')
    failures = []
    for url in github_tarball_urls(repository, revision):
        # 临时包放系统临时目录：放 dest.parent 时，Windows 上解压后文件仍可能被占用，
        # 连带把 TemporaryDirectory 的清理拖成 PermissionError（这个坑我踩过一次）。
        handle, name = tempfile.mkstemp(prefix='shionarium-src-', suffix='.tar.gz')
        os.close(handle)
        temporary = Path(name)
        try:
            _download(url, temporary, timeout=timeout, log=log)
            _extract(temporary, dest)
            if any(dest.iterdir()):
                _say(log, f'✓ 源码来自 {url}')
                return url
            raise ValueError('解压后目录为空')
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError, tarfile.TarError) as error:
            reason = str(error) or type(error).__name__
            failures.append(f'{url} → {reason}')
            _say(log, f'✗ {url} 失败：{reason}')
            for child in dest.iterdir():          # 清掉半成品，换下一个源
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink(missing_ok=True)
        finally:
            for _ in range(5):
                try:
                    temporary.unlink(missing_ok=True)
                    break
                except PermissionError:
                    time.sleep(0.2)
                except OSError:
                    break
    raise RuntimeError(
        '源码下载失败，已尝试的地址：\n' + '\n'.join(failures) +
        '\n可设置 SHIONARIUM_GH_MIRROR 指定可用镜像前缀后重试。')
