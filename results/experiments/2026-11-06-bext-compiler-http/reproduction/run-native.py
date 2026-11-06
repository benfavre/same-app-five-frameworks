from pathlib import Path
import argparse, fcntl, hashlib, importlib.util, json, os, re, shutil, signal, subprocess, time

E = Path(__file__).resolve().parent
R = Path('/home/infra-sj278/bext')
B = E/'source'
policy_path = E/'build-inputs.json'
policy = json.loads(policy_path.read_text())
features = 'nginx-compat,tls,redis,realtime,waf,v8,react-compiler-oxc,turbopack,php,route-css,h3-quic,native-caps,caldav,mqtt,grpc,automonique-term-ws,websocket-proxy,bun-mimalloc'
policy['command'] = ['cargo','+nightly','build','--release','-p','bext-server','--bin','bext-server','--no-default-features','--features',features]
policy_path.write_text(json.dumps(policy,indent=2)+'\n')
external = json.loads((E/'external-dependency-pins.json').read_text())
spec = importlib.util.spec_from_file_location('guard',R/'scripts/qualify-bun-design.py')
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)
parser = argparse.ArgumentParser()
parser.add_argument('--stage',choices=['all','tests','build'],default='all')
args = parser.parse_args()
commands = [('compiler-tests', ['/home/infra-sj278/.cargo/bin/cargo','+nightly','test','--locked','--offline','--release','-p','bext-core','--lib','transform::prism_compile','--','--test-threads=1']),
            ('build', ['/home/infra-sj278/.cargo/bin/cargo',*policy['command'][1:],'--locked','--offline'])]
if args.stage == 'tests': commands = commands[:1]
if args.stage == 'build': commands = commands[1:]

def pins():
    return {p:hashlib.sha256((B/p).read_bytes()).hexdigest() for p in policy['source_sha256']}

def external_changes():
    return [p for p,h in external.items() if not Path(p).is_file() or hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h]

with Path('/home/infra-sj278/.local/state/bext-prism-scaling-20261031/measurement.lock').open('a+') as lock:
    print('Waiting for native measurement/build lock',flush=True)
    fcntl.flock(lock,fcntl.LOCK_EX)
    assert subprocess.run(['pgrep','-x','cargo'],capture_output=True).returncode==1
    assert pins()==policy['source_sha256'],'Private source changed before native work'
    assert not external_changes(),'External dependency changed before native work'
    env = {k:v for k,v in os.environ.items() if not k.startswith('BEXT_')}
    env.update(PATH='/home/infra-sj278/.cargo/bin:'+os.environ.get('PATH','/usr/bin:/bin'),
               BEXT_PHP_CONFIG='/opt/php-zts/bin/php-config',BEXT_STABLE_BUNDLE_ORDER='1',
               CARGO_BUILD_JOBS='4',CARGO_TARGET_DIR=str(R/'target'))
    for name,command in commands:
        assert not (E/(name+'.json')).exists()
        started=time.monotonic();peak=0;reason=None
        print('Starting '+name,flush=True)
        with (E/(name+'.log')).open('w') as log:
            p=subprocess.Popen(command,cwd=B,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            try:
                while p.poll() is None:
                    peak=max(peak,guard.rss_kib(p.pid))
                    available=next(int(l.split()[1]) for l in Path('/proc/meminfo').read_text().splitlines() if l.startswith('MemAvailable:'))
                    if peak>10*1024*1024:reason='Build tree RSS exceeded 10 GiB'
                    elif available<8*1024*1024:reason='Host memory headroom below 8 GiB'
                    elif shutil.disk_usage(B).free<4*1024**3:reason='Disk headroom below 4 GiB'
                    elif time.monotonic()-started>2400:reason='Stage exceeded 40 minutes'
                    if reason:
                        os.killpg(p.pid,signal.SIGKILL)
                        break
                    time.sleep(.5)
            finally:
                if p.poll() is None:os.killpg(p.pid,signal.SIGKILL)
                p.wait()
        unchanged=pins()==policy['source_sha256'];changed=external_changes()
        row=dict(at=time.time(),command=command,exit_code=p.returncode,elapsed_s=time.monotonic()-started,
                 peak_rss_kib=peak,guard=reason,source_pins_unchanged=unchanged,
                 external_inputs_unchanged=not changed,external_changes=changed,production_changed=False,
                 passed=p.returncode==0 and reason is None and unchanged and not changed)
        if name.endswith('tests'):
            found=re.findall(r'test result: ok\. (\d+) passed; (\d+) failed; (\d+) ignored; (\d+) measured; (\d+) filtered out',(E/(name+'.log')).read_text())
            row['test_counts']=[dict(zip(['passed','failed','ignored','measured','filtered'],map(int,x))) for x in found]
            row['passed']=row['passed'] and bool(found) and sum(int(x[0]) for x in found)>0 and all(int(x[1])==0 for x in found)
        elif row['passed']:
            shutil.copy2(R/'target/release/bext-server',E/'bext-server')
            row.update(binary_sha256=hashlib.sha256((E/'bext-server').read_bytes()).hexdigest(),binary_bytes=(E/'bext-server').stat().st_size,
                       BEXT_PHP_CONFIG=env['BEXT_PHP_CONFIG'])
        (E/(name+'.json')).write_text(json.dumps(row,indent=2)+'\n')
        print(name,json.dumps(row),flush=True)
        if not row['passed']:raise SystemExit(1)
