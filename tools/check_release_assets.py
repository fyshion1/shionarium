"""Reject known excluded payloads in default frontend output; not a legal audit."""
from pathlib import Path
import sys


def violations(root):
    return sorted(str(path.relative_to(root)).replace('\\', '/')
                  for path in root.rglob('*') if path.is_file()
                  and (path.suffix.lower() in {'.moc3', '.vrm', '.fbx'}
                       or path.name.lower() in ('live2dcubismcore.min.js',
                                                'aliciasolid_vrm-0.51.vrm')
                       or 'cubismsamples' in {part.lower() for part in path.parts}))


def main():
    root = Path(__file__).resolve().parents[1] / 'frontend/dist'
    if not (root / 'index.html').is_file():
        print('FAIL: build frontend before checking release assets')
        return 1
    errors = violations(root)
    if errors:
        print('FAIL: excluded assets in build:\n' + '\n'.join(errors))
        return 1
    print('PASS: known restricted payloads absent from default frontend build; not a full license audit.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
