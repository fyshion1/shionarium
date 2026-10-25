"""Build a validated appearance ZIP without modifying the source directory."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.services.appearance_packs import Manifest, PackError, parse


def build(source: Path, output: Path):
    if source.is_symlink():
        raise PackError('源码目录不可为符号链接')
    source = source.resolve()
    data = json.loads((source / 'theme.json').read_text(encoding='utf-8-sig'))
    files = {}
    for name in (data.get('font_file'), data.get('background_file')):
        if name:
            path = source / name
            if path.is_symlink() or path.parent.is_symlink() or path.resolve().parent != source / 'assets':
                raise PackError('资源必须是 assets 下的真实文件')
            files[name] = path.read_bytes()
    data['assets'] = {name: hashlib.sha256(content).hexdigest() for name, content in files.items()}
    # The runtime parser is also the build validator; there is one v1 contract.
    files['theme.json'] = (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    for name in ('LICENSE.txt', 'README.md'):
        path = source / name
        if path.is_file() and not path.is_symlink():
            files[name] = path.read_bytes()
    content = io.BytesIO()
    with zipfile.ZipFile(content, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, value in files.items():
            archive.writestr(name, value)
    manifest, _ = parse(content.getvalue())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(content.getvalue())
    print(f'Built {manifest.id} {manifest.version}: {output} ({len(content.getvalue())} bytes)')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path, nargs='?')
    parser.add_argument('output', type=Path)
    parser.add_argument('--schema', action='store_true', help='Write JSON Schema instead of a ZIP')
    args = parser.parse_args()
    if args.schema:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(Manifest.model_json_schema(), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    elif args.source:
        try:
            build(args.source, args.output)
        except (PackError, OSError, ValueError) as error:
            parser.exit(1, f'{error}\n')
    else:
        parser.error('building a ZIP requires source and output')


if __name__ == '__main__':
    main()
