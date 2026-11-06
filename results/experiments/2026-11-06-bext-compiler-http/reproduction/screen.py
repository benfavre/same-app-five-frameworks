from pathlib import Path
import fcntl,hashlib,importlib.util,json,os,re,shutil,subprocess,sys,tempfile,time
from types import SimpleNamespace
from archive import archive_logs

E=Path(__file__).resolve().parent
R=Path('/home/infra-sj278/same-app-five-frameworks')
OUT=R/'results/experiments/2026-11-06-bext-compiler-http'
BASE=Path('/home/infra-sj278/work/bext-site-admission-wait-20261106/bext-server')
SDK=Path('/home/infra-sj278/work/bext-legacy-hash-hint-20261105/reconciled/source/sites/shared/framework')
spec=importlib.util.spec_from_file_location('runner',R/'harness/run-benchmark.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
sys.path.insert(0,str(R/'harness'))
from summarize import summarize_campaign
flags=dict(BEXT_PRISM_PREPARED_PAGES='1',BEXT_V8_LEGACY_HASH_HINT='1',BEXT_V8_MULTIPLEX='0',
           BEXT_PRISM_TOKEN_SCAN='1',BEXT_V8_PREPARED_TEXT='2',BEXT_PRISM_NATIVE_HTML_SCAN='1',BEXT_V8_SITE_WAIT_MS='250')
env={k:v for k,v in os.environ.items() if not k.startswith('BEXT_')}
env.update(PUPPETEER_EXECUTABLE_PATH='/home/infra-sj278/.cache/puppeteer/chrome/linux-152.0.7977.75/chrome-linux64/chrome',NO_COLOR='true')

def write(p,v):p.write_text(json.dumps(v,indent=2)+'\n')

def activate():
    result={'status':'running','cases':[],'fixtureCopiesOnly':True,
            'binarySha256':hashlib.sha256((E/'bext-server').read_bytes()).hexdigest()}
    for key in list(os.environ):
        if key.startswith('BEXT_'):del os.environ[key]
    os.environ.update(env,BEXT_BIN=str(E/'bext-server'),BEXT_SHARED_FRAMEWORK_DIR=str(E/'source/sites/shared/framework'))
    original_root=runner.ROOT
    with tempfile.TemporaryDirectory(prefix='call-plan-activation-',dir=R/'.benchmark-runtime') as temp:
        root=Path(temp);app=root/'apps/bext';app.parent.mkdir()
        shutil.copytree(R/'apps/bext',app,ignore=shutil.ignore_patterns('.bext','node_modules'))
        (app/'src/app/count.ts').write_text('''const Base:any=globalThis.Request;
export const calls={count:0};
(globalThis as any).Request=class extends Base { constructor(...args:any[]) { super(...args);calls.count++; } };
''')
        (app/'src/app/layout.tsx').write_text('''/** @jsxImportSource @bext-stack/framework */
import './count';
import {requestIsUnused} from '@bext-stack/framework/render-plan';
export default function Layout(props:{children?:any}) {return <html><head><title>Compiler probe</title></head><body data-layout-plan={String(requestIsUnused(Layout,'layout'))}>{props.children}</body></html>;}
''')
        (app/'src/app/page.tsx').write_text('''/** @jsxImportSource @bext-stack/framework */
import {calls} from './count';
import {requestIsUnused} from '@bext-stack/framework/render-plan';
export const dynamic='force-dynamic';
export async function loader(){return {stamp:Date.now(),loaderPlan:requestIsUnused(loader)};}
export default function Page(props:any) {const n=calls.count;calls.count=0;return <main data-requests={n} data-loader-plan={String(props.data.loaderPlan)} data-rendered-at={props.data.stamp}>probe</main>;}
''')
        runner.ROOT=root
        try:
            for enabled in [0,1]:
                os.environ['BEXT_TURBOPACK_DISK_CACHE_DIR']=str(E/f'activation-cache-{enabled}')
                options=SimpleNamespace(server_cpus=[10],bext_v8_workers=4,bext_http_workers=1,bext_log_filter='warn',
                    bext_flag=list({**flags,'BEXT_PRISM_CALL_PLANS':str(enabled)}.items()))
                bench=dict(port=18107,start=str(E/'bext-server')+' run . --listen 127.0.0.1:18107')
                with runner.server('bext',bench,E,f'activation-{enabled}',options) as (proc,started):
                    url='http://127.0.0.1:18107/';runner.ready(proc,url,started)
                    samples=[]
                    for n in range(12):
                        code,html=runner.request(url+'?n='+str(n));assert code==200
                        count=int(re.search(r'data-requests="(\d+)"',html)[1])
                        loader=re.search(r'data-loader-plan="(true|false)"',html)[1]=='true'
                        layout=re.search(r'data-layout-plan="(true|false)"',html)[1]=='true'
                        assert count==(0 if enabled else 2),(enabled,count,html)
                        if loader!=bool(enabled) or layout!=bool(enabled):
                            (E/'activation-failure.html').write_text(html)
                            shutil.copytree(root,E/'activation-failed-fixture',dirs_exist_ok=True)
                            raise AssertionError((enabled,loader,layout))
                        samples.append(dict(requestConstructors=count,loaderPlan=loader,layoutPlan=layout))
                    result['cases'].append(dict(enabled=enabled,samples=samples))
        finally:runner.ROOT=original_root
    result['status']='complete';write(OUT/'activation.json',result)
    print('Native HTTP activation: two Requests -> zero, with both compiler facts active',flush=True)

def cell(name,binary,framework,enabled,stage='screen'):
    target=OUT/stage/name
    cmd=[sys.executable,str(R/'harness/run-benchmark.py'),'--frameworks','bext','--repeats','1','--cold-samples','1',
         '--duration','15','--warmup-seconds','20','--concurrency','50','--server-cpus','10','--client-cpus','0-9,11-21,23',
         '--bext-v8-workers','4','--bext-http-workers','1','--bext-log-filter','warn','--output',str(target)]
    for k,v in {**flags,'BEXT_PRISM_CALL_PLANS':str(enabled)}.items():cmd+=['--bext-flag',k+'='+v]
    print(name,flush=True)
    with (E/(name+'.log')).open('w') as log:
        subprocess.run(cmd,cwd=R,env={**env,'BEXT_BIN':str(binary),'BEXT_SHARED_FRAMEWORK_DIR':str(framework)},stdout=log,stderr=subprocess.STDOUT,check=True)
    summary=summarize_campaign(target);write(target/'summary.json',summary)
    row=summary['frameworks'][0]['runs'][0]
    result=dict(name=name,**row,logs=archive_logs(target))
    print(f"  {row['rps']:,.0f} RPS, {row['cpu_ms_per_request']:.4f} CPU ms/request, p99 {row['p99_ms']:.2f}ms",flush=True)
    return result

if __name__ == '__main__':
    with Path('/home/infra-sj278/.local/state/bext-prism-scaling-20261031/measurement.lock').open('a+') as lock:
        print('Waiting for compiler screen lock',flush=True);fcntl.flock(lock,fcntl.LOCK_EX)
        assert json.loads((E/'build.json').read_text())['passed']
        assert json.loads((E/'compiler-tests.json').read_text())['passed']
        os.sched_setaffinity(0,set(range(24))-{10,22})
        # Child benchmark runners must start with the complete CPU set so they
        # can select server CPU 10 before pinning their clients elsewhere.
        activate();os.sched_setaffinity(0,set(range(24)))
        q={'status':'running','cells':[],'productionChanged':False}
        try:
            for name,binary,framework,enabled in [
                ('01-original',BASE,SDK,0),('02-rebuilt-off',E/'bext-server',E/'source/sites/shared/framework',0),
                ('03-rebuilt-on',E/'bext-server',E/'source/sites/shared/framework',1),('04-original-repeat',BASE,SDK,0)]:
                q['cells'].append(cell(name,binary,framework,enabled));write(OUT/'screen.json',q)
            q['status']='complete'
        except Exception as error:q.update(status='failed',error=str(error));raise
        finally:write(OUT/'screen.json',q)
