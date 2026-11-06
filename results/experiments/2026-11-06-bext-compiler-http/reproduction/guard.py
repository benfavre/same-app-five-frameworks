from pathlib import Path
import importlib.util
import json
import os
import shutil
import signal
import subprocess
import sys
import time

E = Path(__file__).resolve().parent
R = Path('/home/infra-sj278/same-app-five-frameworks')
spec = importlib.util.spec_from_file_location('runner', R/'harness/run-benchmark.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
command = [sys.executable, str(R/'harness/compare-bext-multicore.py'),
    '--binary', '/home/infra-sj278/work/bext-legacy-hash-hint-20261105/reconciled/bext-server',
    '--framework', '/home/infra-sj278/work/bext-legacy-hash-hint-20261105/reconciled/source/sites/shared/framework',
    '--output', str(R/'results/experiments/2026-11-06-bext-prism-multicore'),
    '--lock-file', '/home/infra-sj278/.local/state/bext-prism-scaling-20261031/measurement.lock']
env = {k: v for k, v in os.environ.items() if not k.startswith('BEXT_')}
env['PUPPETEER_EXECUTABLE_PATH'] = '/home/infra-sj278/.cache/puppeteer/chrome/linux-152.0.7977.75/chrome-linux64/chrome'
label = 'campaign'
if len(sys.argv) > 1:
    command = json.loads(Path(sys.argv[1]).read_text())
    label = 'qualification'
    env.update(BEXT_BIN='/home/infra-sj278/work/bext-legacy-hash-hint-20261105/reconciled/bext-server',
               BEXT_SHARED_FRAMEWORK_DIR='/home/infra-sj278/work/bext-legacy-hash-hint-20261105/reconciled/source/sites/shared/framework')
result = {'command': command, 'rssCapKiB': 10*1024*1024, 'minimumAvailableKiB': 8*1024*1024,
          'minimumDiskBytes': 4*1024**3, 'timeoutSeconds': 1200, 'productionChanged': False,
          'peakRssKiB': 0, 'minimumObservedAvailableKiB': None, 'guard': None}
started = time.monotonic()
with (E/(label+'.log')).open('w') as log:
    process = subprocess.Popen(command, cwd=R, env=env, stdout=log, stderr=subprocess.STDOUT,
                               start_new_session=True)
    while process.poll() is None:
        tree = runner.process_tree(process.pid)
        rss = 0
        for entry in tree:
            try:
                rss += next(int(line.split()[1]) for line in Path(f"/proc/{entry['pid']}/status").read_text().splitlines() if line.startswith('VmRSS:'))
            except (OSError, StopIteration):
                pass
        available = next(int(line.split()[1]) for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:'))
        result['peakRssKiB'] = max(result['peakRssKiB'], rss)
        result['minimumObservedAvailableKiB'] = min(result['minimumObservedAvailableKiB'] or available, available)
        if rss > result['rssCapKiB']:
            result['guard'] = 'owned process-tree RSS cap exceeded'
        elif available < result['minimumAvailableKiB']:
            result['guard'] = 'host available memory below headroom'
        elif shutil.disk_usage(E).free < result['minimumDiskBytes']:
            result['guard'] = 'disk headroom below limit'
        elif time.monotonic()-started > result['timeoutSeconds']:
            result['guard'] = 'campaign deadline exceeded'
        if result['guard']:
            groups = {process.pid}
            for entry in tree:
                try:
                    group = os.getpgid(entry['pid'])
                    if group != os.getpgrp():
                        groups.add(group)
                except ProcessLookupError:
                    pass
            for sig in [signal.SIGTERM, signal.SIGKILL]:
                for group in groups:
                    try:
                        os.killpg(group, sig)
                    except ProcessLookupError:
                        pass
                time.sleep(1)
            break
        time.sleep(1)
    result.update(exitCode=process.wait(), elapsedSeconds=time.monotonic()-started)
result['passed'] = result['exitCode'] == 0 and result['guard'] is None
(E/('guard.json' if label == 'campaign' else 'guard-qualification.json')).write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result, indent=2), flush=True)
sys.exit(0 if result['passed'] else 1)
