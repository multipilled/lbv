"""Runs a RenderDoc replay script with no visible window: qrenderdoc.exe --python <script> on a hidden desktop.

usage (Windows):
  python -I tools/lab/rdreplay.py <script.py> [--seconds N]
  e.g. RD_CAPTURE=<.rdc> RD_OUT=<folder> python -I tools/lab/rdreplay.py tools/lab/rd/passes.py
       RD_CAPTURE=<.rdc> RD_OUT=<folder> RD_EVENTS=690-790 RD_SAVE=11829 python -I tools/lab/rdreplay.py tools/lab/rd/events.py

The portable RenderDoc 1.47 has no standalone `renderdoc` Python module and no Qt offscreen platform plugin, but
qrenderdoc's embedded Python (3.8) can `import renderdoc` and replay a capture. Its Qt window would show, so it is
started on a desktop of its own (CreateDesktopW, STARTUPINFO.lpDesktop): nothing appears on the user's screen and it
can't take focus or input. The script should write its results to files and end with os._exit(0); the process is
terminated by PID after --seconds (default 300) otherwise. Prints the exit code. The child inherits the environment
(the RD_* variables of the scripts in tools/lab/rd/).
First start of qrenderdoc on a profile: set "Analytics_TotalOptOut": true, "CheckUpdate_AllowChecks": false and
"Tips_HasSeenFirst": true in %APPDATA%\\qrenderdoc\\UI.config, or its first-run prompt blocks the script, invisibly.
"""
import ctypes
import os
import sys
from ctypes import wintypes

QRD = os.environ.get('QRENDERDOC', 'qrenderdoc.exe')
user32 = ctypes.WinDLL('user32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
GENERIC_ALL = 0x10000000
CREATE_NO_WINDOW = 0x08000000
WAIT_TIMEOUT = 0x102


class STARTUPINFOW(ctypes.Structure):
    _fields_ = [('cb', wintypes.DWORD), ('lpReserved', wintypes.LPWSTR), ('lpDesktop', wintypes.LPWSTR),
                ('lpTitle', wintypes.LPWSTR), ('dwX', wintypes.DWORD), ('dwY', wintypes.DWORD),
                ('dwXSize', wintypes.DWORD), ('dwYSize', wintypes.DWORD), ('dwXCountChars', wintypes.DWORD),
                ('dwYCountChars', wintypes.DWORD), ('dwFillAttribute', wintypes.DWORD), ('dwFlags', wintypes.DWORD),
                ('wShowWindow', wintypes.WORD), ('cbReserved2', wintypes.WORD), ('lpReserved2', ctypes.c_void_p),
                ('hStdInput', wintypes.HANDLE), ('hStdOutput', wintypes.HANDLE), ('hStdError', wintypes.HANDLE)]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [('hProcess', wintypes.HANDLE), ('hThread', wintypes.HANDLE), ('dwProcessId', wintypes.DWORD),
                ('dwThreadId', wintypes.DWORD)]


def main():
    script = os.path.abspath(sys.argv[1])
    seconds = int(sys.argv[sys.argv.index('--seconds') + 1]) if '--seconds' in sys.argv else 300
    user32.CreateDesktopW.restype = wintypes.HANDLE
    desk = user32.CreateDesktopW('lbv-rdreplay', None, None, 0, GENERIC_ALL, None)
    if not desk:
        sys.exit(f'CreateDesktopW failed: {ctypes.get_last_error()}')
    si = STARTUPINFOW(cb=ctypes.sizeof(STARTUPINFOW), lpDesktop='lbv-rdreplay')
    pi = PROCESS_INFORMATION()
    cmd = ctypes.create_unicode_buffer(f'"{QRD}" --python "{script}"')
    if not kernel32.CreateProcessW(None, cmd, None, None, False, CREATE_NO_WINDOW, None,
                                   os.path.dirname(script), ctypes.byref(si), ctypes.byref(pi)):
        sys.exit(f'CreateProcessW failed: {ctypes.get_last_error()}')
    print(f'qrenderdoc pid {pi.dwProcessId} on a hidden desktop', flush=True)
    if kernel32.WaitForSingleObject(pi.hProcess, seconds * 1000) == WAIT_TIMEOUT:
        kernel32.TerminateProcess(pi.hProcess, 1)
        kernel32.WaitForSingleObject(pi.hProcess, 10000)
        print(f'terminated pid {pi.dwProcessId} after {seconds} s')
    code = wintypes.DWORD()
    kernel32.GetExitCodeProcess(pi.hProcess, ctypes.byref(code))
    print(f'exit {code.value}')
    kernel32.CloseHandle(pi.hThread)
    kernel32.CloseHandle(pi.hProcess)
    user32.CloseDesktop(desk)


if __name__ == '__main__':
    main()
