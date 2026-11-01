"""M1: builds and runs the kit's dynarmic comparison tests (recomp_tests) per module, as the kit's
recomp/run-tests.ps1 does, but with the venv's python (no bare `python`), the tests already made by
tools/lab/recompile.sh, and the fork's games-only build (build/vita3k-games) for dynarmic.

  tools/with_cpu.sh lbv-m1 <data>/venv/Scripts/python.exe -I tools/lab/recomp_tests.py [module ...]
      [--iterations N] [--fn-iterations N] [--jobs N] [--no-run]

Build trees: build/recomp-<module>; results: build/recomp-<module>/tests.txt (last lines printed).
"""
import os, shutil, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KIT = os.path.join(ROOT, 'third_party', 'recomp')
sys.path.insert(0, os.path.join(KIT, 'tools'))
import msvc  # noqa: E402


def arg(args, name, default):
    if name in args:
        i = args.index(name)
        value = args[i + 1]
        del args[i:i + 2]
        return value
    return default


def main():
    args = sys.argv[1:]
    iterations = arg(args, '--iterations', '256')
    fn_iterations = arg(args, '--fn-iterations', '64')
    jobs = arg(args, '--jobs', '4')
    run = '--no-run' not in args
    modules = [a for a in args if not a.startswith('--')] or ['eboot', 'libc', 'libfios2']
    env = msvc.environment()
    # build-recomp.py and build-vita3k.py start cmake by name; Visual Studio's CMake is not on PATH
    # outside a developer shell (tools/lab/build-fork.sh), and Windows resolves a bare name on the
    # parent's PATH, so cmake is started by its full path
    cmake = shutil.which('cmake', path=env.get('PATH'))
    if not cmake:
        sys.exit('no cmake on the MSVC PATH')
    failed = []
    for m in modules:
        build = os.path.join(ROOT, 'build', f'recomp-{m}')
        configure = [cmake, '-S', os.path.join(KIT, 'recomp'), '-B', build, '-G', 'Ninja',
                     '-DCMAKE_BUILD_TYPE=Release', '-DRECOMP_MODULES=', f'-DRECOMP_TEST_MODULE={m}',
                     f'-DRECOMP_JOBS={jobs}', f'-DGENERATED_DIR={os.path.join(ROOT, "generated")}',
                     f'-DVITA3K_SRC={os.path.join(ROOT, "third_party", "vita3k")}',
                     f'-DVITA3K_BUILD={os.path.join(ROOT, "build", "vita3k-games")}']
        r = subprocess.run(configure, env=env, capture_output=True, text=True)
        if r.returncode:
            print(r.stdout[-2000:], r.stderr[-2000:])
            sys.exit(f'configure failed for {m}')
        r = subprocess.run([cmake, '--build', build, '--target', 'recomp_tests', '--', f'-j{jobs}'],
                           env=env, capture_output=True, text=True)
        if r.returncode:
            errors = [line for line in r.stdout.splitlines() if ' error ' in line or 'error:' in line]
            print('\n'.join(errors[:10]) or r.stdout[-3000:])
            failed.append(m)
            print(f'{m}: build failed')
            continue
        if not run:
            print(f'{m}: built')
            continue
        log = os.path.join(build, 'tests.txt')
        # -Command, not -File: the test's arguments go to guarded-run's -Rest as one array (as
        # run-tests.ps1 passes them); with -File they would bind to -MaxMB and -MaxMinutes
        guard = os.path.join(KIT, 'recomp', 'tests', 'guarded-run.ps1')
        exe = os.path.join(build, 'recomp_tests.exe')
        code = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
                               f"& '{guard}' '{exe}' '{log}' -Rest {int(iterations)}, '*', {int(fn_iterations)}; "
                               'exit $LASTEXITCODE']).returncode
        if not os.path.exists(log):
            print(f'{m}: no {log}')
            failed.append(m)
            continue
        with open(log, encoding='utf-8', errors='replace') as f:
            tail = f.read().splitlines()[-12:]
        print(f'== {m} (exit {code})')
        print('\n'.join(tail))
        if code:
            failed.append(m)
    print('failing: ' + ', '.join(failed) if failed else 'all modules pass')
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
