from screen import *
import statistics

q=json.loads((OUT/'qualification.json').read_text());assert q['status']=='complete'
build=json.loads((E/'build.json').read_text());assert build['passed']
all_campaigns=q['singleCpu']+[q['astroComparison']]+q['fullMachine']+[q['highLoad']]
counts={'warmup200':0,'load200':0,'entries':0}
for c in all_campaigns:
    fresh=summarize_campaign(OUT/'qualification'/c['name'])
    assert fresh['frameworks']==list(c['frameworks'].values())
    for key in ['warmup200','load200']:counts[key]+=c['counts'][key]
    counts['entries']+=sum(row['run_count'] for row in c['frameworks'].values())
q['publicationRecheck']={'status':'passed',**counts,'zeroWarmupLoadErrors':True}
write(OUT/'qualification.json',q)

def line(label,row):
    lo=row.get('rpsMin',row.get('rps_min'));hi=row.get('rpsMax',row.get('rps_max'))
    return f"| {label} | {row['rps']:,.0f} | {lo:,.0f}–{hi:,.0f} | {row['cpu_ms_per_request']:.4f} | {row['p99_ms']:.2f} ms |"
equal=q['astroComparison']['frameworks']
one=q['singleCpuMedians'];full=q['fullMachineMedians']
one_table='| Runtime | Median RPS | RPS min–max | CPU ms/request | p99 |\n|---|---:|---:|---:|---:|\n'+'\n'.join([
    line('Same candidate, flag off',one['0']),line('Same candidate, flag on',one['1']),
    line('Astro, fresh matched comparison',equal['astro']),line('Bext, fresh matched comparison',equal['bext'])])+'\n'
def full_line(label,pool,connections,row):
    lo=row.get('rpsMin',row.get('rps_min'));hi=row.get('rpsMax',row.get('rps_max'))
    cpu=row.get('average_cpu_cores')
    return f"| {label} | {pool} | {connections} | {row['rps']:,.0f} | {lo:,.0f}–{hi:,.0f} | {cpu:.2f} | {row['p99_ms']:.2f} ms |"
full_table='| Compiler Request plan | V8 / HTTP | Connections | Median RPS | RPS min–max | Server CPU equivalents | p99 |\n|---|---|---:|---:|---:|---:|---:|\n'+'\n'.join([
    full_line('Off','12 / 12',50,full['0']),full_line('On','12 / 12',50,full['1']),
    full_line('On','16 / 24',200,q['highLoad']['frameworks']['bext'])])+'\n'
(OUT/'table.md').write_text(one_table+'\n'+full_table)

full_counts={k:sum(c['counts'][k] for c in q['fullMachine']+[q['highLoad']]) for k in ['warmup200','load200']}
on_counts={k:sum(c['counts'][k] for c in q['fullMachine']+[q['highLoad']] if c['enabled']) for k in ['warmup200','load200']}
headline='''## Compiler Request plans — equal CPU budget, 2026-11-06

The compiler now proves when loaders and layouts cannot use their Request input,
so PRISM can skip constructing it. Loaders and HTML still run fresh on every
request. The pass is opt-in with `BEXT_PRISM_CALL_PLANS=1`.

| Framework | RPS median | RPS min–max | CPU ms/request | p99 |
|---|---:|---:|---:|---:|
'''+line('Astro',equal['astro'])+'\n'+line('bext (PRISM), compiler plan on',equal['bext'])+'\n\n'
headline+=f"A separate same-binary flag-off/on comparison measures **{one['0']['rps']:,.0f} → {one['1']['rps']:,.0f} RPS ({one['rpsIncreasePercent']:+.2f}%)**, with CPU/request changing {(-one['cpuReductionPercent']):+.2f}%. Astro {'remains ahead' if equal['astro']['rps']>equal['bext']['rps'] else 'is behind Bext'} in the matched comparison above.\n\n"
headline+='''Each complete server tree shares CPU 10; clients exclude that physical core
and its SMT sibling. Every entry has a 20-second warmup and 15-second load at
50 connections. Flag comparisons use three balanced pairs (AB/BA/AB), and the
Astro/Bext comparison alternates across three sweeps. Every warmup/load/browser,
24-product SSR, fresh-render and CPU-affinity check passes. Profiling and access
logs remain enabled; render-result caching is disabled. Shared-host ranges are
observations, not confidence intervals.

[Compiler change](https://github.com/benfavre/bext/pull/432),
[raw evidence, profiles, controls and identities](results/experiments/2026-11-06-bext-compiler-http/notes.md),
[final qualification](results/experiments/2026-11-06-bext-compiler-http/qualification.json).
Bootstrap reuse was inconsistent and remains unselected.

'''
readme=(R/'README.md').read_text();at=readme.index('## Latest tuned comparison')
readme=readme[:at]+headline+readme[at:].replace('## Latest tuned comparison','## Earlier five-framework tuned comparison',1)
start=readme.index('## Bext PRISM — full-machine throughput, 2026-11-06')
end=readme.index('## Default-settings baseline',start)
section='''## Bext PRISM — full-machine throughput, 2026-11-06

All 24 logical CPUs of the Ryzen 9 5900X (12 physical cores) are available to
the complete server tree. Clients share the host. Three fresh-server entries
per row use 20-second warmups and 15-second loads; profiling, access logs and
fresh rendering stay enabled. The flag-off/on comparison uses the same binary
and SDK in balanced AB/BA/AB order.

'''+full_table+'\n'
section+=f"Compiler plans change median 50-connection throughput **{full['rpsIncreasePercent']:+.2f}%**. All nine full-machine entries pass: **{full_counts['warmup200']:,} warmup and {full_counts['load200']:,} measured HTTP 200 responses**, with zero warmup/load errors. Flag-on entries account for {on_counts['warmup200']:,} warmup and {on_counts['load200']:,} measured HTTP 200 responses. All three 200-connection runs pass the browser/SSR/freshness checks.\n\n"
section+='''The [bounded admission wait](https://github.com/benfavre/bext/pull/430) remains
250 ms with at most 256 waiting requests per site. A full queue or expired
deadline retains 503 + Retry-After. The [earlier disabled-wait control](results/experiments/2026-11-06-bext-site-admission-wait/notes.md)
reproduced 152,122 warmup 503 responses and remains archived. Configured-instance
numbers are separate from the equal-CPU comparison; these short shared-host runs
do not establish a machine ceiling.

[Full raw runs and exact identities](results/experiments/2026-11-06-bext-compiler-http/qualification.json),
[method and validation](results/experiments/2026-11-06-bext-compiler-http/notes.md).

'''
readme=readme[:start]+section+readme[end:]
readme=readme.replace('Keep the same frozen SDK while comparing native binaries.',
'''The compiler-plan follow-up requires the SDK shipped with [PR #432](https://github.com/benfavre/bext/pull/432) and `--bext-flag BEXT_PRISM_CALL_PLANS=1`.
Use `--warmup-seconds 20 --duration 15` for that comparison.

Keep the same frozen SDK while comparing native binaries.''')
(R/'README.md').write_text(readme)

report=OUT/'build-and-tests.json';v=json.loads(report.read_text());v['build.json']=build
v['sourceCommit']=json.loads((E/'build-inputs.json').read_text())['main_head']
v['localManifests']={name:{'path':str(E/name),'sha256':hashlib.sha256((E/name).read_bytes()).hexdigest()} for name in ['build-inputs.json','external-dependency-pins.json']}
v['finalArtifactGuard']=json.loads((E/'guard-qualification.json').read_text())
v['finalActivation']='activation.json';v['finalSourceInvalidation']='call-plan-source-invalidation-final.json'
write(report,v)
notes=OUT/'notes.md';s=notes.read_text();s+='\n## Final artifact qualification\n\n'+one_table+'\n'+full_table+'\n'
s+=f"The final same-binary compiler flag comparison changes one-CPU median RPS {one['rpsIncreasePercent']:+.2f}% and CPU/request {-one['cpuReductionPercent']:+.2f}%. Full-machine 50-connection median RPS changes {full['rpsIncreasePercent']:+.2f}%. All {counts['entries']} final entries pass: {counts['warmup200']:,} warmup and {counts['load200']:,} measured HTTP 200 responses, zero warmup/load errors. Three 200-connection entries pass without 503 responses. Astro {'remains ahead' if equal['astro']['rps']>equal['bext']['rps'] else 'trails Bext'} in the final matched one-CPU comparison.\n\n"
s+=f"Final source is `{v['sourceCommit']}`, native SHA-256 `{build['binary_sha256']}`. [The cache-fingerprint proof](emitter-fingerprint-proof.json), final native HTTP activation and all 18 source/API invalidation cases pass. The initial binary remains at its separately recorded retained path. Initial and final artifacts are never pooled for headline medians. [Strict publication recheck and complete phase data](qualification.json).\n"
notes.write_text(s)
for name in ['qualify.py','screen.py','publish.py']:(OUT/'reproduction'/name).write_bytes((E/name).read_bytes())
print(json.dumps({'counts':counts,'singleCpu':one,'fullMachine':full,'astro':equal['astro']['rps'],'bext':equal['bext']['rps']},indent=2))
