"""Versioned, data-only appearance packs. No CSS, scripts or persona imports."""
from __future__ import annotations

import hashlib
import io
import json
import re
import shutil
import stat
import tempfile
import time
import uuid
import zipfile
import zlib
from pathlib import Path, PurePosixPath
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from ..data_paths import features_root, runtime_root
from .assets import inspect_image

MAX_ARCHIVE = 20 * 1024 * 1024
MAX_EXPANDED = 32 * 1024 * 1024
MAX_MANIFEST = 64 * 1024
PREVIEW_TTL = 3600
ID = re.compile(r'[a-z][a-z0-9]*(?:-[a-z0-9]+)*')
ASSET = re.compile(r'assets/[a-zA-Z0-9][a-zA-Z0-9_-]*(?:\.[a-zA-Z0-9_-]+)*\.(?:png|jpg|webp|woff2)')
Color = Annotated[str, Field(pattern=r'^#[0-9a-fA-F]{6}$')]
AssetName = Annotated[str, Field(pattern=r'^assets/[a-zA-Z0-9][a-zA-Z0-9_.-]*\.(png|jpg|webp|woff2)$', max_length=120)]


class PackError(ValueError):
    pass


class DataModel(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class Palette(DataModel):
    background: Color
    background_soft: Color
    surface: Color
    surface_raised: Color
    text: Color
    text_muted: Color
    text_subtle: Color
    border: Color
    border_strong: Color
    accent: Color
    accent_text: Color
    accent_soft: Color
    mint: Color
    sky: Color


class Colors(DataModel):
    light: Palette
    dark: Palette


class Manifest(DataModel):
    format: Literal['appearance-pack']
    format_version: Literal[1]
    id: str = Field(min_length=1, max_length=64, pattern=r'^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$')
    name: str = Field(min_length=1, max_length=80)
    version: str = Field(max_length=40, pattern=r'^\d+\.\d+\.\d+(?:-[a-zA-Z0-9.-]+)?$')
    author: str = Field(min_length=1, max_length=200)
    license: str = Field(min_length=1, max_length=4000)
    description: str = Field(default='', max_length=2000)
    colors: Colors
    radius: int = Field(default=12, ge=0, le=24)
    font: Literal['system', 'serif', 'monospace'] = 'system'
    font_file: AssetName | None = None
    background_file: AssetName | None = None
    background_opacity: float = Field(default=0.12, ge=0, le=0.4)
    assets: dict[AssetName, Annotated[str, Field(pattern=r'^[a-f0-9]{64}$')]] = Field(default_factory=dict, max_length=16)

    @model_validator(mode='after')
    def references(self):
        if not all(value.strip() for value in (self.name, self.author, self.license)):
            raise ValueError('名称、作者和许可不能为空')
        for name in self.assets:
            if not ASSET.fullmatch(name):
                raise ValueError('资源必须使用 assets/ 下的普通文件名')
        referenced = {name for name in (self.font_file, self.background_file) if name}
        if referenced != set(self.assets):
            raise ValueError('资源必须全部声明并由字体或背景引用')
        if self.font_file and not self.font_file.endswith('.woff2'):
            raise ValueError('字体只支持 WOFF2')
        if self.background_file and not self.background_file.endswith(('.png', '.jpg', '.webp')):
            raise ValueError('背景只支持 PNG、JPEG 或 WebP')
        return self


def root():
    return runtime_root() / 'appearance-packs'


def _manifest(content: bytes) -> Manifest:
    if len(content) > MAX_MANIFEST:
        raise PackError('theme.json 不能超过 64 KB')
    try:
        data = json.loads(content.decode('utf-8-sig'))
        if not isinstance(data, dict) or type(data.get('format_version')) is not int:
            raise ValueError('format_version 必须为整数')
        return Manifest.model_validate(data)
    except (ValueError, UnicodeError, ValidationError) as error:
        raise PackError(f'外观包清单无效：{error}') from error


def _check_asset(name: str, content: bytes, digest: str):
    if hashlib.sha256(content).hexdigest() != digest:
        raise PackError(f'资源校验失败：{name}')
    if name.endswith('.woff2'):
        if len(content) < 48 or content[:4] != b'wOF2':
            raise PackError('字体不是有效的 WOFF2 文件')
    else:
        try:
            _, extension = inspect_image(content)
        except ValueError as error:
            raise PackError(str(error)) from error
        if not name.endswith('.' + extension):
            raise PackError('背景图片扩展名与内容不一致')


def parse(content: bytes):
    if not content or len(content) > MAX_ARCHIVE:
        raise PackError('外观包不能为空，且不能超过 20 MB')
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            entries = archive.infolist()
            if len(entries) > 32 or sum(e.file_size for e in entries) > MAX_EXPANDED:
                raise PackError('外观包文件数量或展开体积超限')
            names = set()
            files = {}
            for entry in entries:
                name = entry.filename
                path = PurePosixPath(name)
                if (name.casefold() in names or '\\' in name or ':' in name or path.is_absolute()
                        or '..' in path.parts or str(path) != name.rstrip('/')
                        or stat.S_ISLNK(entry.external_attr >> 16) or entry.flag_bits & 1):
                    raise PackError('外观包包含重复、加密或危险路径')
                names.add(name.casefold())
                if entry.is_dir():
                    if name != 'assets/':
                        raise PackError('外观包只允许 assets 资源目录')
                    continue
                if name not in ('theme.json', 'LICENSE.txt', 'README.md') and not ASSET.fullmatch(name):
                    raise PackError('只允许 theme.json、许可说明和声明的图片/字体，不接受代码或 CSS')
                if name in ('theme.json', 'LICENSE.txt', 'README.md') and entry.file_size > MAX_MANIFEST:
                    raise PackError('清单和说明文件不能超过 64 KB')
                files[name] = archive.read(entry)
            manifest = _manifest(files.get('theme.json', b''))
            if set(files) - {'theme.json', 'LICENSE.txt', 'README.md'} != set(manifest.assets):
                raise PackError('资源声明与包内文件不一致')
            for name, digest in manifest.assets.items():
                _check_asset(name, files[name], digest)
            return manifest, files
    except (zipfile.BadZipFile, KeyError, RuntimeError, NotImplementedError, OSError, zlib.error) as error:
        raise PackError('无法读取外观包 ZIP') from error


def _read_folder(folder: Path):
    if (folder.is_symlink() or not folder.is_dir()
            or folder.resolve() != folder.parent.resolve() / folder.name):
        raise PackError('外观目录不可为符号链接')
    manifest_path = folder / 'theme.json'
    if manifest_path.is_symlink() or manifest_path.stat().st_size > MAX_MANIFEST:
        raise PackError('外观清单路径或体积无效')
    manifest = _manifest(manifest_path.read_bytes())
    total = 0
    for name, digest in manifest.assets.items():
        asset = folder / name
        if (asset.is_symlink() or asset.parent.is_symlink() or not asset.is_file()
                or asset.resolve().parent != folder.resolve() / 'assets'):
            raise PackError('外观资源路径无效')
        total += asset.stat().st_size
        if total > MAX_EXPANDED:
            raise PackError('外观资源体积超限')
        _check_asset(name, asset.read_bytes(), digest)
    return manifest


def catalog():
    items, errors, locations = [], [], {}
    for base, source in ((root(), 'imported'), (features_root(), 'plugin')):
        if not base.is_dir():
            continue
        for folder in sorted(base.iterdir()):
            if folder.name.startswith('.') or not (folder / 'theme.json').exists():
                continue
            try:
                manifest = _read_folder(folder)
                if source == 'plugin':
                    from ..plugin_state import enabled
                    if not enabled(manifest.id):
                        continue
                if manifest.id in locations:
                    raise PackError('外观 ID 重复；请为不同外观使用不同 ID')
                locations[manifest.id] = folder
                items.append({**manifest.model_dump(), 'source': source})
            except (PackError, OSError) as error:
                errors.append({'folder': folder.name, 'message': str(error)})
    return {'items': items, 'errors': errors}, locations


def stage(content: bytes):
    manifest, files = parse(content)
    data, _ = catalog()
    if any(item['id'] == manifest.id for item in data['items']):
        raise PackError('同 ID 外观已安装，请先移除旧包；不会覆盖现有文件')
    staging = root() / '.staging'
    staging.mkdir(parents=True, exist_ok=True)
    for old in staging.iterdir():
        if old.is_file() and old.stat().st_mtime < time.time() - PREVIEW_TTL:
            old.unlink()
    # Bound previews even when a client repeatedly uploads within the TTL.
    if sum(p.stat().st_size for p in staging.iterdir() if p.is_file()) + len(content) > 4 * MAX_ARCHIVE:
        raise PackError('待确认外观包过多，请一小时后重试')
    token = uuid.uuid4().hex
    (staging / (token + '.zip')).write_bytes(content)
    return {'token': token, 'manifest': manifest.model_dump(), 'size': len(content)}


def install(token: str):
    if not re.fullmatch(r'[a-f0-9]{32}', token):
        raise PackError('无效的预览标识')
    archive = root() / '.staging' / (token + '.zip')
    if not archive.is_file() or archive.stat().st_mtime < time.time() - PREVIEW_TTL:
        raise PackError('预览已过期，请重新选择外观包')
    manifest, files = parse(archive.read_bytes())
    data, _ = catalog()
    target = root() / manifest.id
    if target.exists() or target.is_symlink() or any(item['id'] == manifest.id for item in data['items']):
        raise PackError('同 ID 外观已存在，请先移除旧包')
    temporary = Path(tempfile.mkdtemp(prefix='.install-', dir=root()))
    try:
        for name, content in files.items():
            destination = temporary / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
        temporary.rename(target)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    archive.unlink()
    return {'id': manifest.id}


def uninstall(identifier: str):
    if not ID.fullmatch(identifier) or len(identifier) > 64:
        raise PackError('外观 ID 无效')
    data, locations = catalog()
    item = next((item for item in data['items'] if item['id'] == identifier), None)
    if not item or item['source'] != 'imported':
        raise PackError('只能在此移除导入的外观包；插件目录中的包请由其安装方式管理')
    folder = locations[identifier]
    archive = root() / '.removed'
    archive.mkdir(exist_ok=True)
    folder.rename(archive / (identifier + '-' + uuid.uuid4().hex))
    return {'ok': True}


def asset_file(identifier: str, filename: str):
    if not ID.fullmatch(identifier) or not ASSET.fullmatch('assets/' + filename):
        raise PackError('无效的外观资源路径')
    data, locations = catalog()
    item = next((item for item in data['items'] if item['id'] == identifier), None)
    name = 'assets/' + filename
    if not item or name not in item['assets']:
        raise PackError('外观资源不存在')
    return locations[identifier] / name
