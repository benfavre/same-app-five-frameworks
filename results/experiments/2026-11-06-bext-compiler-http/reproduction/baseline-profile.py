from pathlib import Path
import fcntl,hashlib,importlib.util,json,os,subprocess,sys,tempfile,time
from types import SimpleNamespace
from archive import archive_logs

E=Path(__file__).resolve().parent
R=Path('/home/infra-sj278/same-app-five-frameworks')
OUT=R/'results/experiments/2026-11-06-bext-compiler-http'
spec=importlib.util.spec_from_file_location('runner',R/'harness/run-benchmark.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
sys.path.insert(0,str(R/'harness'))
from summarize import summarize_campaign,table
flags={'BEXT_PRISM_PREPARED_PAGES':'1','BEXT_V8_LEGACY_HASH_HINT':'1','BEXT_V8_MULTIPLEX':'0',
       'BEXT_PRISM_TOKEN_SCAN':'1','BEXT_V8_PREPARED_TEXT':'2','BEXT_PRISM_NATIVE_HTML_SCAN':'1','BEXT_V8_SITE_WAIT_MS':'250'}
env={k:v for k,v in os.environ.items() if not k.startswith('BEXT_')}
env.update(BEXT_BIN='/home/infra-sj278/work/bext-site-admission-wait-20261106/bext-server',
    BEXT_SHARED_FRAMEWORK_DIR='/home/infra-sj278/work/bext-legacy-hash-hint-20261105/reconciled/source/sites/shared/framework',
    PUPPETEER_EXECUTABLE_PATH='/home/infra-sj278/.cache/puppeteer/chrome/linux-152.0.7977.75/chrome-linux64/chrome',NO_COLOR='true')

def write(p,v):p.write_text(json.dumps(v,indent=2)+'\n')

with Path('/home/infra-sj278/.local/state/bext-prism-scaling-20261031/measurement.lock').open('a+') as lock:
    print('Waiting for baseline/profile lock',flush=True);fcntl.flock(lock,fcntl.LOCK_EX)
    OUT.mkdir(parents=True,exist_ok=False)
    command=[sys.executable,str(R/'harness/run-benchmark.py'),'--frameworks','astro','bext',
        '--repeats','3','--cold-samples','1','--duration','15','--warmup-seconds','20','--concurrency','50',
        '--server-cpus','10','--client-cpus','0-9,11-21,23','--bext-v8-workers','4','--bext-http-workers','1',
        '--bext-log-filter','warn','--output',str(OUT/'baseline')]
    for k,v in flags.items():command+=['--bext-flag',k+'='+v]
    print('Fresh equal-CPU Astro/Bext baseline',flush=True)
    with (E/'baseline.log').open('w') as log:
        subprocess.run(command,cwd=R,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
    summary=summarize_campaign(OUT/'baseline');write(OUT/'baseline/summary.json',summary)
    (OUT/'baseline/table.md').write_text(table(summary))
    write(OUT/'baseline/log-retention.json',archive_logs(OUT/'baseline'))
    print(table(summary),flush=True)
    for k in list(os.environ):
        if k.startswith('BEXT_'):del os.environ[k]
    os.environ.update(env,**flags)
    os.sched_setaffinity(0,set(range(24))-{10,22})
    profile=OUT/'http-profile';profile.mkdir()
    q=dict(status='running',kind='whole HTTP server-tree diagnostic; profiled RPS is not a headline measurement',
           flags=flags,serverCpu=[10],productionChanged=False,
           binarySha256=hashlib.file_digest(Path(env['BEXT_BIN']).open('rb'),'sha256').hexdigest())
    try:
        bench=json.loads((R/'apps/bext/bench.json').read_text())
        args=SimpleNamespace(server_cpus=[10],bext_v8_workers=4,bext_http_workers=1,bext_log_filter='warn',bext_flag=list(flags.items()))
        with runner.server('bext',bench,profile,'server',args) as (server,started):
            url='http://127.0.0.1:8105/';runner.ready(server,url,started)
            with tempfile.NamedTemporaryFile(mode='w') as urls:
                urls.writelines(f'{url}?r={n}\n' for n in range(runner.LOAD_URL_COUNT));urls.flush()
                base=['oha','-c','50','-w','--no-tui','--http-version','1.1','--output-format','json','--urls-from-file',urls.name]
                with (profile/'warmup.json').open('w') as out:
                    subprocess.run(base+['-z','20s'],stdout=out,stderr=subprocess.DEVNULL,check=True,timeout=50)
                runner.require_http_200(json.loads((profile/'warmup.json').read_text()),'profile warmup')
                processes=runner.process_tree(server.pid);write(profile/'processes.json',processes)
                audit=runner.CpuAudit(server.pid,[10]);audit.start()
                perf=None;load=None
                try:
                    with (profile/'perf.log').open('w') as log,(profile/'oha.json').open('w') as output:
                        perf=subprocess.Popen(['perf','record','-o',str(E/'http-perf.data'),'-e','cpu-clock','-F','199',
                            '--call-graph','dwarf,8192','-p',','.join(str(p['pid']) for p in processes),'--','sleep','12'],
                            stdout=log,stderr=subprocess.STDOUT)
                        load=subprocess.Popen(base+['-z','12s'],stdout=output,stderr=subprocess.DEVNULL)
                        time.sleep(1);stamps=[]
                        for n in range(20):stamps.append(runner.stamp(url+'?r=profile-'+str(n)));time.sleep(.1)
                        assert load.wait(timeout=40)==0 and perf.wait(timeout=25)==0
                        assert len(set(stamps))==20
                        write(profile/'proof.json',dict(loadSamples=stamps,uncached=True))
                finally:
                    for proc in [perf,load]:
                        if proc is not None and proc.poll() is None:proc.terminate();proc.wait(timeout=5)
                    cpu=audit.stop();write(profile/'cpu.json',cpu)
                runner.require_http_200(json.loads((profile/'oha.json').read_text()),'profile load')
                assert not cpu['errors'] and not cpu['affinityViolations']
                q['cpuRoles']={role:sum(p['cpuSeconds'] for p in cpu['processes'] if (p['pid']==server.pid)==(role=='controller'))
                               for role in ['controller','workers']}
        for name,opts in [('flat.txt',['--no-children']),('inclusive.txt',['--children','--sort','symbol'])]:
            with (profile/name).open('w') as report:
                subprocess.run(['perf','report','-i',str(E/'http-perf.data'),'--stdio','--no-inline','--call-graph','none',
                                '--percent-limit','0.25',*opts],stdout=report,stderr=subprocess.DEVNULL,check=True,timeout=60)
        q.update(status='complete',perfDataPath=str(E/'http-perf.data'),perfDataSha256=hashlib.file_digest((E/'http-perf.data').open('rb'),'sha256').hexdigest())
    except Exception as error:q.update(status='failed',error=str(error));raise
    finally:write(profile/'qualification.json',q)
    print('HTTP profile complete',q['cpuRoles'],flush=True)
