from screen import *
import statistics

identity=None
def campaign(name,enabled=1,repeats=1,frameworks=('bext',),full=False,connections=50,v8=4,http=1):
    global identity
    target=OUT/'qualification'/name
    cpus='0-23' if full else '10'
    clients='0-23' if full else '0-9,11-21,23'
    cmd=[sys.executable,str(R/'harness/run-benchmark.py'),'--frameworks',*frameworks,
         '--repeats',str(repeats),'--cold-samples','1','--duration','15','--warmup-seconds','20',
         '--concurrency',str(connections),'--server-cpus',cpus,'--client-cpus',clients,
         '--bext-v8-workers',str(v8),'--bext-http-workers',str(http),'--bext-log-filter','warn','--output',str(target)]
    for k,v in {**flags,'BEXT_PRISM_CALL_PLANS':str(enabled)}.items():cmd+=['--bext-flag',k+'='+v]
    print(name,flush=True)
    with (E/('qualification-'+name+'.log')).open('w') as log:
        subprocess.run(cmd,cwd=R,env={**env,'BEXT_BIN':str(E/'bext-server'),
                       'BEXT_SHARED_FRAMEWORK_DIR':str(E/'source/sites/shared/framework')},stdout=log,stderr=subprocess.STDOUT,check=True)
    summary=summarize_campaign(target);write(target/'summary.json',summary)
    meta=json.loads((target/'metadata.json').read_text())
    current={key:meta['bext'][key] for key in ['binarySha256','frameworkSha256']}
    current['benchmarkSource']=meta['sourceSha256']
    if identity is None:identity=current
    assert identity==current,'Runtime, SDK or benchmark source drifted'
    counts={'warmup200':0,'load200':0}
    for p in target.glob('run-*/*.warmup.json'):
        dist=json.loads(p.read_text())['statusCodeDistribution'];assert set(dist)=={'200'}
        counts['warmup200']+=dist['200']
    for p in target.glob('run-*/*.oha.json'):
        dist=json.loads(p.read_text())['statusCodeDistribution'];assert set(dist)=={'200'}
        counts['load200']+=dist['200']
    rows={row['id']:row for row in summary['frameworks']}
    result=dict(name=name,enabled=enabled,repeats=repeats,serverCpus=cpus,connections=connections,
                v8Workers=v8,httpWorkers=http,frameworks=rows,counts=counts,logs=archive_logs(target))
    print('  '+', '.join(f"{fw}: {row['rps']:,} RPS, p99 {row['p99_ms']:.2f}ms" for fw,row in rows.items()),flush=True)
    return result

def paired(cells):
    medians={}
    for enabled in [0,1]:
        rows=[c['frameworks']['bext']['runs'][0] for c in cells if c['enabled']==enabled]
        medians[str(enabled)]={k:statistics.median(c[k] for c in rows) for k in ['rps','p99_ms','cpu_ms_per_request','average_cpu_cores']}
        medians[str(enabled)].update(rpsMin=min(c['rps'] for c in rows),rpsMax=max(c['rps'] for c in rows))
    medians['rpsIncreasePercent']=(medians['1']['rps']/medians['0']['rps']-1)*100
    medians['cpuReductionPercent']=(1-medians['1']['cpu_ms_per_request']/medians['0']['cpu_ms_per_request'])*100
    return medians

with Path('/home/infra-sj278/.local/state/bext-prism-scaling-20261031/measurement.lock').open('a+') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX)
    result={'status':'running','productionChanged':False,'responseCache':False,
            'method':'same-artifact flag off/on AB/BA/AB; alternating Astro/Bext; full-machine off/on AB/BA/AB; high-load candidate',
            'singleCpu':[],'astroComparison':None,'fullMachine':[],'highLoad':None}
    try:
        assert json.loads((E/'build.json').read_text())['passed']
        activate()
        command=[sys.executable,str(R/'harness/check-prepared-source.py'),'--output',str(OUT/'call-plan-source-invalidation-final.json'),'--legacy-hash-hint','1']
        with (E/'source-invalidation-final.log').open('w') as log:
            subprocess.run(command,cwd=R,env={**env,**flags,'BEXT_PRISM_CALL_PLANS':'1',
                'BEXT_BIN':str(E/'bext-server'),'BEXT_SHARED_FRAMEWORK_DIR':str(E/'source/sites/shared/framework')},
                stdout=log,stderr=subprocess.STDOUT,check=True)
        print('Final artifact: HTTP activation and 18 source/API freshness cases passed',flush=True)
        for pair,order in enumerate([[0,1],[1,0],[0,1]],1):
            for enabled in order:
                result['singleCpu'].append(campaign(f'single-{pair}-{enabled}',enabled));write(OUT/'qualification.json',result)
        result['singleCpuMedians']=paired(result['singleCpu'])
        result['astroComparison']=campaign('astro-bext',frameworks=('astro','bext'),repeats=3)
        write(OUT/'qualification.json',result)
        for pair,order in enumerate([[0,1],[1,0],[0,1]],1):
            for enabled in order:
                result['fullMachine'].append(campaign(f'full-{pair}-{enabled}',enabled,full=True,v8=12,http=12));write(OUT/'qualification.json',result)
        result['fullMachineMedians']=paired(result['fullMachine'])
        result['highLoad']=campaign('high-load',full=True,connections=200,v8=16,http=24,repeats=3)
        policy=json.loads((E/'build-inputs.json').read_text())
        changed=[p for p,h in policy['source_sha256'].items() if hashlib.sha256((E/'source'/p).read_bytes()).hexdigest()!=h]
        assert not changed,('Source pins changed',changed)
        result.update(status='complete',identity=identity,sourcePinsUnchanged=True)
    except Exception as error:result.update(status='failed',error=str(error));raise
    finally:write(OUT/'qualification.json',result)
