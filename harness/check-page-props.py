#!/usr/bin/env python3
"""Compare rendered page props from the original, rebuilt-control and direct paths."""
import argparse
import html
import http.client
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('runner',ROOT/'harness/run-benchmark.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)

PAGE='''export const dynamic = "force-dynamic";
export async function action() { return {ok: true}; }
export async function loader({request, params}: any) {
  return {params, request: {url: request.url, method: request.method,
    headers: Object.fromEntries(request.headers.entries()), body: await request.text()}};
}
export default function Page(props: any) {
  return <pre id="props-probe">{JSON.stringify(props)}</pre>;
}
'''

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['original','candidate','framework','output']:parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--port',type=int,default=18107)
    args=parser.parse_args();args.output=args.output.resolve();args.output.mkdir(parents=True,exist_ok=False)
    os.sched_setaffinity(0,set(range(24))-{10,22})
    cases=[
        ('empty','GET','/',[],None),
        ('repeats','GET','/?z=last&a=1&a=2&bare&empty=',[],None),
        ('unicode','GET','/?x=%C3%A9%F0%9F%98%80&quote=%22%3C%26',[],None),
        ('invalid-percent','GET','/?%FF=%FF&bad=%ZZ&plus=a+b',[],None),
        ('params','GET','/probe/alpha/beta?q=value',[],None),
        ('cookies','GET','/',[('Cookie','a=1'),('Cookie','b=2')],None),
        ('repeated-header','GET','/',[('X-List','one'),('X-List','two')],None),
        ('proxy','GET','/?value=proxy',[('X-Forwarded-Proto','https'),('X-Forwarded-Host','example.test:8443')],None),
        ('utf8-body','POST','/?value=posted',[('Content-Type','text/plain')],'é😀\0<&>"'.encode()),
        ('empty-body','POST','/',[],b''),
        ('binary-body','POST','/',[('Content-Type','application/octet-stream')],b'\xff\x00bytes'),
        ('post-params','POST','/probe/one/two?r=1&r=2',[('Cookie','a=1'),('Cookie','b=2')],b'posted'),
    ]
    report=dict(status='running',cases=[],productionChanged=False,scope='page props wire compatibility; not a load benchmark')
    reference={};original_root=runner.ROOT
    try:
        for arm,binary,flag in [('original',args.original,0),('rebuilt-control',args.candidate,0),('direct',args.candidate,1)]:
            os.environ['BEXT_SHARED_FRAMEWORK_DIR']=str(args.framework.resolve())
            with tempfile.TemporaryDirectory(prefix='page-props-',dir=ROOT/'.benchmark-runtime') as temporary:
                root=Path(temporary);app=root/'apps/bext';app.parent.mkdir()
                shutil.copytree(ROOT/'apps/bext',app,ignore=shutil.ignore_patterns('.bext','node_modules'))
                for relative in ['src/app/page.tsx','src/app/probe/[id]/[part]/page.tsx']:
                    page=app/relative;page.parent.mkdir(parents=True,exist_ok=True);page.write_text(PAGE)
                runner.ROOT=root
                options=SimpleNamespace(server_cpus=[10],bext_v8_workers=4,bext_http_workers=1,bext_log_filter='warn',
                    bext_flag=[('BEXT_V8_MULTIPLEX','0'),('BEXT_PRISM_PREPARED_PAGES','1'),('BEXT_V8_LEGACY_HASH_HINT','1'),
                        ('BEXT_PRISM_TOKEN_SCAN','1'),('BEXT_V8_PREPARED_TEXT','2'),('BEXT_PRISM_NATIVE_HTML_SCAN','1'),
                        ('BEXT_PRISM_DIRECT_PROPS_JSON',str(flag))])
                bench=dict(port=args.port,start='BEXT_PRISM_RENDER_CACHE=0 '+str(binary.resolve())+
                    f' run . --listen 127.0.0.1:{args.port}')
                with runner.server('bext',bench,args.output,arm,options) as (proc,started):
                    runner.ready(proc,f'http://127.0.0.1:{args.port}/',started)
                    for name,method,path,headers,body in cases:
                        connection=http.client.HTTPConnection('127.0.0.1',args.port,timeout=5)
                        try:
                            connection.putrequest(method,path)
                            connection.putheader('User-Agent','bext-props-wire-check')
                            for key,value in headers:connection.putheader(key,value)
                            if body is not None:connection.putheader('Content-Length',str(len(body)))
                            connection.endheaders(body)
                            response=connection.getresponse();source=response.read().decode()
                            assert response.status==200,(arm,name,response.status,source[:200])
                        finally:connection.close()
                        match=re.search(r'<pre id="props-probe">([\s\S]*?)</pre>',source)
                        assert match,(arm,name,'missing props probe')
                        encoded=html.unescape(match[1]);props=json.loads(encoded)
                        assert props['data']['request']['method']==method,(arm,name,props)
                        expected_body=body.decode() if body and name!='binary-body' else ''
                        assert props['data']['request']['body']==expected_body,(arm,name,props)
                        if name in ['params','post-params']:assert len(props['params'])==2
                        if name in ['cookies','post-params']:assert props['data']['request']['headers']['cookie']=='a=1; b=2'
                        if arm=='original':reference[name]=encoded
                        else:assert encoded==reference[name],(arm,name,'JSON bytes differ',reference[name],encoded)
                        report['cases'].append(dict(arm=arm,case=name,status=response.status,propsJson=encoded))
                runner.ROOT=original_root
        report['status']='complete'
    except Exception as error:
        report.update(status='failed',error=str(error));raise
    finally:
        runner.ROOT=original_root;runner.write_json(args.output/'proof.json',report)

if __name__=='__main__':main()
