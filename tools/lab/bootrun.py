"""One focus-free, muted run of the lbv front end, with scripted input, then closed by PID.

usage (Windows, run it through tools/with_cpu.sh and tools/with_lock.sh):
  python -I tools/lab/bootrun.py <folder with lbv.exe> "<v3kdrive steps>" [--dump-elfs] [--seconds N]
                                 [--fps <csv>] [--normal-priority]

- lbv.exe starts with its window shown without activation (STARTUPINFO SW_SHOWNOACTIVATE and SDL's
  SDL_WINDOW_ACTIVATE_WHEN_SHOWN/RAISED=0), at below-normal priority (unless --normal-priority), with the input pipe on
  (VITA3K_INPUT_PIPE=v3kdrive). Sound: the folder's lbv.ini must have volume = 0 ([audio]); the
  script refuses to start otherwise.
- The steps go to the kit's v3kdrive.py `run` (input pipe, PrintWindow and pipe screenshots, no focus).
- --fps <csv>: v3kdrive's FPS samples (window title, every 500 ms during `wait` steps) go to <csv>.
- --normal-priority: lbv.exe at normal priority, as the shared GPU lane keeps game runs; with every CPU slot
  busy (below-normal builds and tests at 100% CPU) a below-normal run got 0.3 cores, booted 4x slower and hung in
  the intro video (M3c c3-c7).
- --dump-elfs: SSD_DUMP_ELFS=1, so the fork writes every module as loaded to <folder>/lbv/elfdumps/.
- Focus guard: the run starts with Windows' crash and error dialogs off (SetErrorMode, inherited by lbv.exe),
  and a watcher thread kills lbv.exe by PID at the first sign that it could take focus: its window in the
  foreground, a dialog window of its own (class #32770), or a fatal line in its log ("NativeCPU: no native
  code", "abort() called", an unhandled exception). The reason is printed ("guard: killed ...").
- The foreground window is also sampled before, during and after; a change to an lbv window is reported.
- The process's CPU time (user + kernel) is printed before it is closed.
- The process is closed with WM_CLOSE, then terminated by PID if it is still there after 10 s.
"""
import ctypes
import os
import re
import subprocess
import sys
import threading
import time
from ctypes import wintypes

user32 = ctypes.WinDLL('user32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
KIT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'third_party', 'recomp', 'tools')
SW_SHOWNOACTIVATE = 4
STARTF_USESHOWWINDOW = 1
BELOW_NORMAL_PRIORITY_CLASS = 0x4000
WM_CLOSE = 0x10
# SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX | SEM_NOOPENFILEERRORBOX: no Windows Error Reporting or
# critical-error dialog for the child (the error mode is inherited)
QUIET_ERROR_MODE = 0x0001 | 0x0002 | 0x8000
FATAL_LOG = re.compile(r'NativeCPU: no native code|abort\(\) called|std::terminate|Unhandled exception|EXCEPTION_')


def windows_of(pid):
    out = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _):
        p = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
        if p.value == pid:
            out.append(hwnd)
        return True
    user32.EnumWindows(cb, 0)
    return out


def foreground_pid():
    p = wintypes.DWORD()
    user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), ctypes.byref(p))
    return p.value


def class_of(hwnd):
    buf = ctypes.create_unicode_buffer(64)
    user32.GetClassNameW(hwnd, buf, 64)
    return buf.value


def guard(proc, log, started, stop, reasons):
    """kills proc at the first sign it could take focus; reasons gets why"""
    pos = 0
    while not stop.is_set() and proc.poll() is None:
        why = None
        if foreground_pid() == proc.pid:
            why = 'its window came to the foreground'
        else:
            for hwnd in windows_of(proc.pid):
                if user32.IsWindowVisible(hwnd) and class_of(hwnd) == '#32770':
                    why = 'it opened a dialog'
                    break
        try:
            if os.path.getmtime(log) >= started:
                with open(log, 'rb') as f:
                    if os.path.getsize(log) < pos:
                        pos = 0
                    f.seek(pos)
                    text = f.read().decode('utf-8', 'replace')
                    pos = f.tell()
                m = FATAL_LOG.search(text)
                if m and not why:
                    why = f'its log says "{m.group(0)}"'
        except OSError:
            pass
        if why:
            proc.kill()
            reasons.append(why)
            print(f'guard: killed pid {proc.pid} at {time.time() - started:.1f} s: {why}', flush=True)
            return
        time.sleep(0.1)


def cpu_seconds(pid):
    """user + kernel CPU time of the process so far (GetProcessTimes), in seconds"""
    h = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return None
    t = [wintypes.FILETIME() for _ in range(4)]
    ok = kernel32.GetProcessTimes(h, *[ctypes.byref(x) for x in t])
    kernel32.CloseHandle(h)
    return sum((x.dwHighDateTime << 32 | x.dwLowDateTime) for x in t[2:]) / 1e7 if ok else None


def main():
    fps = sys.argv[sys.argv.index('--fps') + 1] if '--fps' in sys.argv else None
    args = [a for a in sys.argv[1:] if not a.startswith('--') and a != fps]
    folder, steps = os.path.abspath(args[0]), args[1]
    seconds = int(sys.argv[sys.argv.index('--seconds') + 1]) if '--seconds' in sys.argv else 0
    ini = open(os.path.join(folder, 'lbv.ini'), encoding='utf-8').read()
    if not re.search(r'^\s*volume\s*=\s*0\s*$', ini, re.M):
        sys.exit('lbv.ini: set volume = 0 under [audio] first (runs are muted)')

    env = dict(os.environ, VITA3K_INPUT_PIPE='v3kdrive', SDL_WINDOW_ACTIVATE_WHEN_SHOWN='0',
               SDL_WINDOW_ACTIVATE_WHEN_RAISED='0')
    if '--dump-elfs' in sys.argv:
        env['SSD_DUMP_ELFS'] = '1'
    si = subprocess.STARTUPINFO()
    si.dwFlags |= STARTF_USESHOWWINDOW
    si.wShowWindow = SW_SHOWNOACTIVATE
    before = foreground_pid()
    kernel32.SetErrorMode(QUIET_ERROR_MODE)
    proc = subprocess.Popen([os.path.join(folder, 'lbv.exe')], cwd=folder, env=env, startupinfo=si,
                            creationflags=0 if '--normal-priority' in sys.argv else BELOW_NORMAL_PRIORITY_CLASS,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    started = time.time()
    print(f'lbv.exe pid {proc.pid}; foreground pid before: {before}', flush=True)
    stolen = []
    stop = threading.Event()
    threading.Thread(target=guard, args=(proc, os.path.join(folder, 'lbv', 'vita3k.log'), started, stop, stolen),
                     daemon=True).start()
    try:
        drive = [sys.executable, '-I', os.path.join(KIT, 'v3kdrive.py'), folder]
        opts = ['--exe', 'lbv.exe', '--title', 'LittleBigPlanet']
        # wait for the game window to show its FPS (v3kdrive's `run` looks for that title)
        end = time.time() + 120
        while time.time() < end and proc.poll() is None:
            r = subprocess.run(drive + ['title'] + opts, capture_output=True, text=True)
            if re.search(r'LittleBigPlanet.*FPS', r.stdout):
                print('window:', r.stdout.strip(), flush=True)
                break
            time.sleep(2)
        if foreground_pid() == proc.pid:
            stolen.append('at start')
        r = subprocess.run(drive + ['run', steps] + ([fps] if fps else []) + opts, text=True)
        if foreground_pid() == proc.pid:
            stolen.append('after the steps')
        end = time.time() + seconds
        while time.time() < end and proc.poll() is None:
            time.sleep(1)
    finally:
        stop.set()
        cpu = cpu_seconds(proc.pid) if proc.poll() is None else None
        if cpu is not None:
            wall = time.time() - started
            print(f'cpu: {cpu:.1f} s user+kernel in {wall:.1f} s ({cpu / wall:.2f} cores on average)', flush=True)
        for hwnd in windows_of(proc.pid):
            user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
        try:
            proc.wait(10)
        except subprocess.TimeoutExpired:
            proc.terminate()
            proc.wait(10)
        print(f'closed pid {proc.pid} (exit {proc.returncode}); foreground pid after: {foreground_pid()}; '
              f'focus taken: {", ".join(stolen) if stolen else "no"}', flush=True)


if __name__ == '__main__':
    main()
