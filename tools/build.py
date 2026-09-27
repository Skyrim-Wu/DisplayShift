"""Build on each target OS: python tools/build.py. Does not install dependencies."""
import platform
import subprocess
import sys
import tkinter
from pathlib import Path

root = Path(__file__).resolve().parents[1]
system = platform.system()
if system not in ('Windows', 'Darwin'):
    raise SystemExit('Build on Windows or macOS.')
# Fail before producing an unusable artifact if Tcl is inaccessible in this environment.
tkinter.Tcl().eval('info patchlevel')
subprocess.run([
    sys.executable, '-m', 'PyInstaller', '--clean', '--noconfirm', '--windowed', '--onedir',
    '--name', 'DisplayShift', '--hidden-import',
    'pynput.keyboard._darwin' if system == 'Darwin' else 'pynput.keyboard._win32',
    '--hidden-import', 'pynput.mouse._darwin' if system == 'Darwin' else 'pynput.mouse._win32',
    str(root / 'displayshift.py'),
], cwd=root, check=True)
