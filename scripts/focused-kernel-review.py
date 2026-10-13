import json, os, pathlib, subprocess, urllib.request, shutil
root = pathlib.Path(os.environ['RUNNER_TEMP']) / 'kernel-review'
root.mkdir()
project = pathlib.Path.cwd()
lean = pathlib.Path(subprocess.check_output(['which','lean'],text=True).strip()).resolve()
stdlib = lean.parent.parent / 'lib/lean'
search = [stdlib]
for package in (project / '.lake/packages').iterdir():
    artifacts = package / '.lake/build/lib/lean'
    if artifacts.is_dir(): search.append(artifacts.resolve())
records=[]
for target in json.loads(pathlib.Path('review-targets.json').read_text()):
    local = root / str(target['number'])
    local.mkdir()
    for path in target['paths']:
        source = local / path
        source.parent.mkdir(parents=True, exist_ok=True)
        url='https://raw.githubusercontent.com/SlopDotCash/proximityprize/'+target['head']+'/'+path
        source.write_bytes(urllib.request.urlopen(url,timeout=30).read())
    env={'PATH':'/usr/bin:/bin','HOME':str(local),'TMPDIR':str(local),'LEAN_PATH':os.pathsep.join(map(str,[local,*search]))}
    for path in target['paths']:
        source=local/path
        args=['sudo','unshare','--net','--', '/usr/bin/env','-i', *[k+'='+v for k,v in env.items()],str(lean),'-o',str(source.with_suffix('.olean')),str(source)]
        result=subprocess.run(args,cwd=local,capture_output=True,text=True,timeout=300)
        print('PR',target['number'],target['head'],path,'EXIT',result.returncode,flush=True)
        print(result.stdout+result.stderr,flush=True)
        records.append({'pr':target['number'],'head':target['head'],'path':path,'exit':result.returncode,'output':result.stdout+result.stderr})
        if result.returncode or 'sorryAx' in result.stdout: raise SystemExit(1)
pathlib.Path('kernel-review-results.json').write_text(json.dumps(records,indent=2))
