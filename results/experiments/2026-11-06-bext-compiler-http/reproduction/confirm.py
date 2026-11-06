from screen import *
import statistics

arms={
    'original':(BASE,SDK,0),
    'call-plans':(E/'bext-server',E/'source/sites/shared/framework',1),
    'bootstrap':(BASE,E/'bootstrap-source/sites/shared/framework',0),
}
with Path('/home/infra-sj278/.local/state/bext-prism-scaling-20261031/measurement.lock').open('a+') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX)
    result={'status':'running','method':'ABC/BCA/CAB; three fresh-server cells per arm','cells':[],
            'productionChanged':False,'responseCache':False}
    try:
        command=[sys.executable,str(R/'harness/check-prepared-source.py'),'--output',str(OUT/'call-plan-source-invalidation.json'),'--legacy-hash-hint','1']
        with (E/'source-invalidation.log').open('w') as log:
            subprocess.run(command,cwd=R,env={**env,**flags,'BEXT_PRISM_CALL_PLANS':'1',
                'BEXT_BIN':str(E/'bext-server'),'BEXT_SHARED_FRAMEWORK_DIR':str(E/'source/sites/shared/framework')},
                stdout=log,stderr=subprocess.STDOUT,check=True)
        print('Compiler source/API invalidation: passed',flush=True)
        identities={};source=None
        sequence=0
        for block in range(3):
            names=list(arms);names=names[block:]+names[:block]
            for arm in names:
                sequence+=1;name=f'{sequence:02d}-{arm}'
                row=cell(name,*arms[arm],stage='confirmation')
                metadata=json.loads((OUT/'confirmation'/name/'metadata.json').read_text())
                if source is None:source=metadata['sourceSha256']
                assert source==metadata['sourceSha256'],'Benchmark source drift'
                identity={key:metadata['bext'][key] for key in ['binarySha256','frameworkSha256']}
                if arm in identities:assert identity==identities[arm],f'{arm} identity drift'
                identities[arm]=identity
                result['cells'].append(dict(block=block+1,arm=arm,**row));write(OUT/'confirmation.json',result)
        result['medians']={}
        for arm in arms:
            rows=[c for c in result['cells'] if c['arm']==arm]
            result['medians'][arm]={k:statistics.median(c[k] for c in rows) for k in ['rps','p99_ms','cpu_ms_per_request']}
            result['medians'][arm].update(rpsMin=min(c['rps'] for c in rows),rpsMax=max(c['rps'] for c in rows))
        result.update(status='complete',identities=identities)
    except Exception as error:result.update(status='failed',error=str(error));raise
    finally:write(OUT/'confirmation.json',result)
