import hashlib,re,subprocess
def archive_logs(directory):
    result=[]
    for f in sorted(directory.glob('run-*/bext.server.log')):
        digest=hashlib.sha256();statuses={};rx=re.compile(rb'"status":(\d+)')
        with f.open('rb') as stream:
            for line in stream:
                digest.update(line)
                if b'"method":"' in line:
                    match=rx.search(line)
                    if match:
                        key=match[1].decode();statuses[key]=statuses.get(key,0)+1
        compressed=f.with_suffix('.log.zst')
        subprocess.run(['zstd','-q','-T2','-1','--keep',str(f),'-o',str(compressed)],check=True)
        verify=hashlib.sha256()
        with subprocess.Popen(['zstd','-q','-dc',str(compressed)],stdout=subprocess.PIPE) as decoder:
            for chunk in iter(lambda:decoder.stdout.read(1024*1024),b''):verify.update(chunk)
            assert decoder.wait()==0
        assert verify.hexdigest()==digest.hexdigest()
        result.append(dict(originalPath=str(f),path=str(compressed),compression='zstd',
                           originalSha256=digest.hexdigest(),bytes=f.stat().st_size,
                           compressedSha256=hashlib.sha256(compressed.read_bytes()).hexdigest(),
                           compressedBytes=compressed.stat().st_size,statusDistribution=statuses,retainedLocally=True))
        f.unlink() # task-owned generated log; verified lossless archive retained
    return result
