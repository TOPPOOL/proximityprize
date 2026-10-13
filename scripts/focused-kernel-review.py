import json, os, pathlib, subprocess, urllib.request, shutil
root = pathlib.Path(os.environ['RUNNER_TEMP']) / 'kernel-review'
root.mkdir()
project = pathlib.Path.cwd()
lean = pathlib.Path(subprocess.check_output(['elan','which','lean'],text=True).strip()).resolve()
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
    mounts=['--ro-bind',str(lean.parent.parent),'/toolchain','--bind',str(local),'/work']
    paths=['/work','/toolchain/lib/lean']
    for index, artifacts in enumerate(search[1:]):
        destination='/deps/'+str(index)
        mounts += ['--ro-bind',str(artifacts),destination]
        paths.append(destination)
    for system in ('/usr','/lib','/lib64'):
        if pathlib.Path(system).exists(): mounts += ['--ro-bind',system,system]
    env=['--setenv','HOME','/work','--setenv','TMPDIR','/tmp','--setenv','LEAN_PATH',':'.join(paths)]
    for path in target['paths']:
        source=local/path
        args=['sudo','bwrap','--unshare-all','--die-with-parent','--clearenv',*mounts,'--proc','/proc','--dev','/dev','--tmpfs','/tmp','--chdir','/work',*env,'/toolchain/bin/lean','-o','/work/'+str(pathlib.Path(path).with_suffix('.olean')),'/work/'+path]
        result=subprocess.run(args,cwd=local,capture_output=True,text=True,timeout=300)
        print('PR',target['number'],target['head'],path,'EXIT',result.returncode,flush=True)
        print(result.stdout+result.stderr,flush=True)
        records.append({'pr':target['number'],'head':target['head'],'path':path,'exit':result.returncode,'output':result.stdout+result.stderr})
        pathlib.Path('kernel-review-results.json').write_text(json.dumps(records,indent=2))
        if result.returncode or 'sorryAx' in result.stdout: raise SystemExit(1)
pathlib.Path('kernel-review-results.json').write_text(json.dumps(records,indent=2))
