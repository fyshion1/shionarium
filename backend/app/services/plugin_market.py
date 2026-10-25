"""Curated GitHub source installs and optional components, explicitly initiated locally."""
from datetime import datetime, timezone
import importlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import uuid

import psutil

from .. import components, plugin_state
from ..data_paths import PROJECT_ROOT, features_root, runtime_root
from ..file_lock import acquire
from ..features_registry import folder_has_payload
from . import mirror_sources

JOBS = runtime_root() / 'plugin-installs'
BACKEND = PROJECT_ROOT / 'backend'
CATALOG = [
    dict(id='desktop_pet', name='桌宠', kind='plugin', folder='desktop-pet',
         description='在桌面显示角色、收发聊天；安装 Electron 和前端依赖，不自动启动。',
         repository='fyshion1/desktop-pet', revision='10e0c7012b195994a80c88f69a60385add48738b',
         size='Electron 及前端依赖通常需要数百 MB', available=True),
    dict(id='qq_bridge', name='QQ 桥', kind='plugin', folder='qq-bridge',
         description='将 QQ 消息接入聊天。安装桥的 Python 依赖；QQ 账号和网关需另行配置。',
         repository='fyshion1/qq-bridge', revision='13f0503fe1a70c60ec27d5e392c232e382decd9e',
         size='Python 依赖；QQ 网关另装', available=True),
    dict(id='tools', name='联网搜索', kind='plugin', folder='tools',
         description='让助手搜索网络资料；部分来源还需浏览器扩展与登录。',
         repository='fyshion1/tools', revision='unpublished', size='工具运行库和搜索 CLI',
         available=False, reason='插件仓库尚未公开，当前不能为新用户下载安装。'),
    dict(id='local_voice', name='本地说话与听写', kind='component',
         description='ASR 把声音转成文字，TTS 把回复念出来。安装 Paraformer 中英识别、Piper 中文音色和运行库。Piper 运行库采用 GPL-3.0-or-later；华燕音色的上游模型卡将数据集许可标为 Unknown，不能据此承诺商用或再分发权。处理在本机进行，聊天模型仍按配置调用。',
         revision='1', size='数百 MB，使用 CPU，无需独立显卡', available=True),
    dict(id='qq_asr', name='QQ 语音转写', kind='component',
         description='识别 QQ 语音，支持网关转写失败时本地兜底。仅安装识别与解码，不安装朗读音色。',
         revision='1', size='数百 MB，已有识别模型会复用', available=True),
    dict(id='online_voice', name='在线朗读', kind='component',
         description='安装 Edge TTS 运行库，通过在线服务朗读文字，需要可用网络；不安装本地音色。',
         revision='1', size='小型 Python 依赖', available=True),
    dict(id='memory_search', name='本地语义检索', kind='component',
         description='用意思相近的表述找回记忆和资料。安装 BGE-small 中文向量模型和 PyTorch 等运行库。不安装仍可关键词检索，也可自行配置外部 Embedding API（可能收费）。',
         revision='1', size='模型约 100 MB，完整依赖可能数 GB', available=True),
]


class MarketError(Exception):
    pass


def entry(identifier):
    item = next((dict(row) for row in CATALOG if row['id'] == identifier), None)
    if item is None:
        raise MarketError('未知市场条目；只接受目录中列出的项目')
    return item


def component_ready(identifier):
    if identifier == 'online_voice':
        return components.package_present('edge_tts')
    if identifier in ('qq_asr', 'local_voice'):
        ready = (components.local_asr_ready() and components.package_present('sherpa_onnx')
                 and components.package_present('pilk') and components.package_present('imageio_ffmpeg'))
        return ready and (identifier == 'qq_asr' or components.piper_ready())
    model = BACKEND / 'data/models/embedding/BAAI__bge-small-zh-v1.5'
    return (components.package_present('sentence_transformers')
            and all((model / name).is_file() and (model / name).stat().st_size > 0
                    for name in ('config.json', 'config_sentence_transformers.json', 'modules.json',
                                 'sentence_bert_config.json', 'model.safetensors', 'tokenizer.json',
                                 'tokenizer_config.json', 'special_tokens_map.json', 'vocab.txt',
                                 '1_Pooling/config.json')))


def catalog():
    items = []
    for row in CATALOG:
        item = dict(row)
        if item['kind'] == 'plugin':
            target = features_root() / item['folder']
            item.update(installed=folder_has_payload(target), occupied=target.exists(),
                        url='https://github.com/' + item['repository'])
        else:
            item.update(installed=component_ready(item['id']), occupied=False)
        items.append(item)
    return dict(items=items, note='目录随内核发布，下载使用固定 GitHub 提交；无中心账号或付费市场服务。安装不会自动启用插件或启动账号连接。')


def save(job):
    JOBS.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=JOBS, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as output:
            json.dump(job, output, ensure_ascii=False)
        os.replace(name, JOBS / (job['id'] + '.json'))
    finally:
        Path(name).unlink(missing_ok=True)


def read_job(identifier):
    if not re.fullmatch(r'[a-f0-9]{32}', identifier):
        raise MarketError('无效的安装任务')
    try:
        job = json.loads((JOBS / (identifier + '.json')).read_text(encoding='utf-8'))
    except FileNotFoundError as exc:
        raise MarketError('安装任务不存在') from exc
    if job['status'] == 'running':
        try:
            alive = psutil.Process(job['owner_pid']).create_time() == job['owner_created']
        except psutil.Error:
            alive = False
        if not alive:
            job.update(status='failed', message='服务在安装完成前退出；未确认成功，请检查后重试。', phase='安装中断')
    return job


def jobs():
    paths = sorted(JOBS.glob('*.json'), key=lambda path: path.stat().st_mtime, reverse=True)[:10]
    return [read_job(path.stem) for path in paths]


def active():
    JOBS.mkdir(parents=True, exist_ok=True)
    with (JOBS / 'install.lock').open('a+b') as handle:
        return not acquire(handle)


def command(args, cwd, log, label, env=None):
    environment = os.environ.copy()
    environment.update(PYTHONIOENCODING='utf-8', GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='Never')
    if env:
        environment.update(env)
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    try:
        with log.open('ab') as output:
            process = subprocess.Popen([str(arg) for arg in args], cwd=cwd, env=environment,
                                       stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
                                       creationflags=flags)
            try:
                code = process.wait(timeout=1800)
            except subprocess.TimeoutExpired:
                children = psutil.Process(process.pid).children(recursive=True)
                for child in reversed(children):
                    try:
                        child.kill()
                    except psutil.NoSuchProcess:
                        pass
                process.kill();process.wait(timeout=15)
                raise
    except subprocess.TimeoutExpired as exc:
        raise MarketError(f'{label}超时。请检查网络和下载源后重试，不会自动切换代理。') from exc
    if code:
        raise MarketError(f'{label}失败（退出码 {code}）。请检查网络、磁盘空间与仓库权限；详细日志保存在本机 plugin-installs 目录。')


def _tool(name: str, *fallbacks: str):
    """找可执行文件：PATH 优先，找不到再试几个常见安装位置。

    后端不一定继承到完整的用户 PATH（从启动器/服务拉起来时尤其容易缺 node 或 uv），
    只靠 shutil.which 会直接报「未找到 npm」，把环境问题误报成缺依赖。
    """
    found = shutil.which(name)
    if found:
        return found
    for candidate in fallbacks:
        expanded = os.path.expandvars(candidate)
        if Path(expanded).is_file():
            return expanded
    return None


def _npm():
    return _tool('npm',
                 r'C:\Program Files\nodejs\npm.cmd',
                 r'%APPDATA%\npm\npm.cmd',
                 r'%LOCALAPPDATA%\Programs\nodejs\npm.cmd')


def _uv():
    return _tool('uv',
                 r'%USERPROFILE%\.local\bin\uv.exe',
                 r'%LOCALAPPDATA%\Microsoft\WinGet\Links\uv.exe')


def _with_tool_path(env: dict, *tools) -> dict:
    """把工具所在目录补进子进程 PATH。

    npm 的 postinstall（Electron 的 `node install.js`、以及各种 `npm run`）是按名字找
    `node` 的。如果后端没继承到含 Node.js 的 PATH，即使我们用绝对路径调到了 npm，
    脚本里那句 `node` 依然会「不是内部或外部命令」。所以这里把它补上。
    """
    directories = []
    for tool in tools:
        if not tool:
            continue
        directory = str(Path(tool).parent)
        if directory not in directories:
            directories.append(directory)
    if not directories:
        return env
    merged = dict(env)
    current = merged.get('PATH') or os.environ.get('PATH', '')
    merged['PATH'] = os.pathsep.join(directories + ([current] if current else []))
    return merged


def install_plugin(item, job, log):
    root = features_root().resolve()
    root.mkdir(parents=True, exist_ok=True)
    target = root / item['folder']
    if target.exists() or target.is_symlink():
        raise MarketError('插件目录已存在；不会覆盖源码、已有依赖或用户配置。')
    # Stage on the destination filesystem; failed downloads are never installed plugins.
    with tempfile.TemporaryDirectory(prefix='.install-', dir=root) as temporary:
        stage = Path(temporary) / item['folder']
        stage.mkdir()
        # 用 codeload 的 tar 包而不是 `git fetch`：国内 `github.com` 的 git 协议常被重置，
        # 而 codeload 可用；镜像顺序与降级由 mirror_sources 统一负责。也不再依赖本机装 git。
        job['phase'] = '下载源码'; save(job)
        try:
            mirror_sources.fetch_github_tarball(item['repository'], item['revision'], stage, log)
        except RuntimeError as error:
            raise MarketError(str(error)) from error
        if not folder_has_payload(stage):
            raise MarketError('源码校验失败：下载内容不完整或缺少插件入口文件')
        job['phase'] = '安装依赖'; save(job)
        if item['id'] == 'desktop_pet':
            npm = _npm()
            if not npm:
                raise MarketError('未找到 npm，请先安装 Node.js 并重启应用。')
            # 国内镜像：npm 包 + Electron 二进制（后者在 GitHub Releases，直连常超时）。
            # 同时补 PATH：postinstall 里那句 `node install.js` 是按名字找 node 的。
            node_env = _with_tool_path(mirror_sources.npm_env(), _tool('node', str(Path(npm).with_name('node.exe'))), npm)
            command([npm, 'ci'], stage, log, '安装桌宠依赖', node_env)
            command([npm, 'run', 'build'], stage, log, '构建桌宠', node_env)
        else:
            uv = _uv()
            if not uv:
                raise MarketError('未找到 uv，请先安装 uv 并重启应用。')
            command([uv, 'pip', 'install', '--python', sys.executable, '-r', stage / 'requirements.txt'],
                    stage, log, '安装 QQ 桥依赖', mirror_sources.pip_env())
        if target.exists() or target.is_symlink():
            raise MarketError('目标目录在安装过程中发生变化，未覆盖原目录')
        # Disable before publication, so a request cannot auto-load new trusted code.
        plugin_state.update(item['id'], disabled=True)
        stage.rename(target)


def worker(item, job, handle):
    log = JOBS / (job['id'] + '.log')
    try:
        if item['kind'] == 'plugin':
            install_plugin(item, job, log)
        else:
            job['phase'] = '安装运行库与模型'; save(job)
            # 组件安装走 install-features.py；它内部会调 uv / HuggingFace，
            # 这里把 PyPI 与 HF 镜像一起注入，避免模型走 huggingface.co 超时。
            command([sys.executable, PROJECT_ROOT / 'install-features.py', '--install', item['id']],
                    PROJECT_ROOT, log, '安装可选组件',
                    {'VIRTUAL_ENV': sys.prefix, **mirror_sources.install_env()})
            importlib.invalidate_caches()
            if not component_ready(item['id']):
                raise MarketError('安装命令已结束，但运行库或模型检测未通过；请查看本机日志后重试。')
        job.update(status='succeeded', phase='安装完成',
                   message='已下载并安装依赖。插件保持关闭，请重启后端后在“已安装”中启用并应用修改；账号、模型与网关需自行配置。'
                   if item['kind'] == 'plugin' else '组件已安装，请重启后端并刷新页面。未修改已有模型、语音或记忆配置。')
    except Exception as error:
        message = str(error) if isinstance(error, MarketError) else f'安装未完成（{type(error).__name__}）。请检查目录权限、磁盘空间与本机日志后重试。'
        job.update(status='failed', phase='安装失败', message=message)
    finally:
        try:
            save(job)
        finally:
            handle.close()


def start(identifier, revision, accepted):
    item = entry(identifier)
    if not accepted:
        raise MarketError('请先确认允许下载并安装可信代码和依赖')
    if not item['available']:
        raise MarketError(item['reason'])
    if item['revision'] != revision:
        raise MarketError('目录版本已变化，请刷新后重新确认')
    JOBS.mkdir(parents=True, exist_ok=True)
    handle = (JOBS / 'install.lock').open('a+b')
    if not acquire(handle):
        handle.close()
        raise MarketError('已有安装任务进行中，请等待完成')
    job = None
    try:
        if item['kind'] == 'plugin' and ((features_root() / item['folder']).exists()
                                         or (features_root() / item['folder']).is_symlink()):
            raise MarketError('插件目录已存在，不会覆盖，请到“已安装”管理或先恢复本地备份。')
        if item['kind'] == 'component' and component_ready(item['id']):
            raise MarketError('组件已安装，不需要重复安装')
        job = dict(id=uuid.uuid4().hex, item_id=identifier, name=item['name'], revision=revision,
                   status='running', phase='准备安装', message='',
                   created_at=datetime.now(timezone.utc).isoformat(), owner_pid=os.getpid(),
                   owner_created=psutil.Process().create_time())
        save(job)
        threading.Thread(target=worker, args=(item, job, handle), daemon=True, name='plugin-install').start()
        return dict(job)
    except Exception:
        try:
            if job is not None:
                job.update(status='failed', phase='启动失败', message='无法启动安装任务，请稍后重试。')
                save(job)
        finally:
            handle.close()
        raise
