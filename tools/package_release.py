"""Archive a native build without losing macOS executable modes or symlinks."""
import argparse
import hashlib
import platform
import re
import shutil
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--version', required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'v\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?', args.version):
        parser.error('Expected a version such as v0.1.0')
    root = Path(__file__).resolve().parents[1]
    dist = root / 'dist'
    output = dist / 'release'
    output.mkdir(exist_ok=True)
    if platform.system() == 'Darwin':
        app = dist / 'DisplayShift.app'
        if not (app / 'Contents/MacOS/DisplayShift').is_file():
            parser.error('Build dist/DisplayShift.app first')
        archive = output / f'DisplayShift-{args.version}-macOS-arm64.zip'
        subprocess.run(['ditto', '-c', '-k', '--sequesterRsrc', '--keepParent', str(app), str(archive)], check=True)
    elif platform.system() == 'Windows':
        app = dist / 'DisplayShift'
        if not (app / 'DisplayShift.exe').is_file():
            parser.error('Build dist/DisplayShift first')
        shutil.copy2(root / 'RELEASE-README.md', app / '使用说明.md')
        base = output / f'DisplayShift-{args.version}-Windows-x64'
        archive = Path(shutil.make_archive(str(base), 'zip', dist, 'DisplayShift'))
    else:
        parser.error('Unsupported release platform')
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(archive.suffix + '.sha256').write_text(f'{digest}  {archive.name}\n', encoding='ascii')
    print(archive)


if __name__ == '__main__':
    main()
