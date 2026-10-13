import json, os, pathlib, subprocess, urllib.request, shutil, importlib.util, sys
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
    mounts=['-v',str(lean.parent.parent)+':/toolchain:ro','-v',str(local)+':/work:rw']
    paths=['/work','/toolchain/lib/lean']
    for index, artifacts in enumerate(search[1:]):
        destination='/deps/'+str(index)
        mounts += ['-v',str(artifacts)+':'+destination+':ro']
        paths.append(destination)
    for path in target['paths']:
        source=local/path
        args=['docker','run','--rm','--user',str(os.getuid())+':'+str(os.getgid()),'--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--tmpfs','/tmp',*mounts,'-w','/work','-e','HOME=/work','-e','LEAN_PATH='+':'.join(paths),'ubuntu:24.04','/toolchain/bin/lean','-o','/work/'+str(pathlib.Path(path).with_suffix('.olean')),'/work/'+path]
        result=subprocess.run(args,cwd=local,capture_output=True,text=True,timeout=300)
        print('PR',target['number'],target['head'],path,'EXIT',result.returncode,flush=True)
        print(result.stdout+result.stderr,flush=True)
        records.append({'pr':target['number'],'head':target['head'],'path':path,'exit':result.returncode,'output':result.stdout+result.stderr})
        pathlib.Path('kernel-review-results.json').write_text(json.dumps(records,indent=2))
        if result.returncode or 'sorryAx' in result.stdout: raise SystemExit(1)
    if target['number']==233:
        for name in ('proximity_prize_cleanroom_audit.py','proximity_prize_cleanroom_targets.txt'):
            url='https://raw.githubusercontent.com/SlopDotCash/proximityprize/'+target['head']+'/scripts/'+name
            (local/name).write_bytes(urllib.request.urlopen(url,timeout=30).read())
        spec=importlib.util.spec_from_file_location('checked_audit',local/'proximity_prize_cleanroom_audit.py')
        checker=importlib.util.module_from_spec(spec)
        sys.modules['checked_audit']=checker
        spec.loader.exec_module(checker)
        entries=[e for e in checker.parse_manifest(local/'proximity_prize_cleanroom_targets.txt') if e.status=='active']
        (local/'ApexAudit.lean').write_text(checker.build_probe(entries))
        command=args.copy()
        command[-3:] = ['/work/ApexAudit.olean','/work/ApexAudit.lean']
        # Preserve -o; replace the final two path arguments, not the option.
        command=args[:-2]+['/work/ApexAudit.olean','/work/ApexAudit.lean']
        result=subprocess.run(command,cwd=local,capture_output=True,text=True,timeout=600)
        print('APEX AUDIT EXIT',result.returncode,flush=True)
        print(result.stdout+result.stderr,flush=True)
        reports=checker.parse_axioms(result.stdout)
        failures=[]
        for entry in entries:
            if entry.decl not in reports or reports[entry.decl]-checker.ALLOWED_AXIOMS:
                failures.append(entry.decl+': missing/forbidden axiom report')
            failures.extend(checker.check_signature(entry,result.stdout))
        print('APEX CHECKER FAILURES',failures,flush=True)
        records.append({'pr':233,'head':target['head'],'path':'ApexAudit.lean','exit':result.returncode,'output':result.stdout,'checker_failures':failures})
        pathlib.Path('kernel-review-results.json').write_text(json.dumps(records,indent=2))
        if result.returncode or failures: raise SystemExit(1)
pathlib.Path('kernel-review-results.json').write_text(json.dumps(records,indent=2))
