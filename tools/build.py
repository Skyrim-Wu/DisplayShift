"""Build a self-contained app on its target OS: python tools/build.py."""
import argparse
import platform
import subprocess
import sys
import tkinter
from pathlib import Path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--m1ddc', type=Path, help='Patched arm64 m1ddc to embed (required on Mac)')
    parser.add_argument('--distpath', type=Path, default=Path('dist'))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    system = platform.system()
    if system not in ('Windows', 'Darwin'):
        parser.error('Build on Windows or macOS.')
    tkinter.Tcl().eval('info patchlevel')
    command = [sys.executable, '-m', 'PyInstaller', '--clean', '--noconfirm',
               '--windowed', '--onedir', '--name', 'DisplayShift', '--noupx',
               '--distpath', str(args.distpath.resolve()),
               '--add-data', f'{root / "RELEASE-README.md"}:.',
               '--hidden-import', 'pynput.keyboard._darwin' if system == 'Darwin' else 'pynput.keyboard._win32',
               '--hidden-import', 'pynput.mouse._darwin' if system == 'Darwin' else 'pynput.mouse._win32']
    if system == 'Darwin':
        if platform.machine() != 'arm64':
            parser.error('The m1ddc release supports Apple Silicon (arm64) only.')
        helper = (args.m1ddc or root / '.tools/m1ddc/m1ddc').resolve()
        license_file = helper.parent / 'LICENSE'
        if not helper.is_file() or not license_file.is_file():
            parser.error('Build the patched m1ddc first; its LICENSE must be beside it. See README.')
        command += ['--target-architecture', 'arm64', '--osx-bundle-identifier',
                    'io.github.skyrim-wu.displayshift', '--add-binary', f'{helper}:bin',
                    '--add-data', f'{license_file}:licenses/m1ddc']
    subprocess.run([*command, str(root / 'displayshift.py')], cwd=root, check=True)


if __name__ == '__main__':
    main()
