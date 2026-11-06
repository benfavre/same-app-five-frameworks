from screen import *
with Path('/home/infra-sj278/.local/state/bext-prism-scaling-20261031/measurement.lock').open('a+') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX)
    result={'status':'running','cells':[],'productionChanged':False}
    try:
        for name,binary,framework in [
            ('05-rebuilt-frozen-sdk',E/'bext-server',SDK),
            ('06-original-new-sdk',BASE,E/'source/sites/shared/framework')]:
            result['cells'].append(cell(name,binary,framework,0));write(OUT/'isolate.json',result)
        result['status']='complete'
    except Exception as error:result.update(status='failed',error=str(error));raise
    finally:write(OUT/'isolate.json',result)
