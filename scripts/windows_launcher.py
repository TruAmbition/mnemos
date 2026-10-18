"""Windowless Windows launcher; keep the separate runtime's stdio usable by MCP."""
from pathlib import Path
import subprocess
import sys

if __name__ == '__main__':
    executable = Path(sys.executable).with_name('Mnemos.exe')
    try:
        subprocess.Popen([str(executable)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
    except OSError:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, 'Keep Open Mnemos.exe beside Mnemos.exe and the _internal folder. Extract the whole download before opening it.', 'Mnemos could not start', 0)
