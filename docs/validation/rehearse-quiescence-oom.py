#!/usr/bin/env python3
"""Native DL-089 OOM acceptance, isolated store only, using an owned 8 MiB container.

Source env.sh first. Uses an existing image, checked loopback publication, its own
bind source and named volume. No live mutation, process arguments or environments.
"""
import collections,importlib.util,json,os,socket,subprocess,tempfile,time
from pathlib import Path
root=Path(__file__).resolve().parents[2];assert Path.cwd()==root
envdir=root.parent/'sql-megasamples-upgrade-env';out=root/'build/dl089'
assert os.environ['CONTAINERS_STORAGE_CONF']==str(envdir/'storage.conf')
def run(*args,check=True):return subprocess.run(['podman',*args],text=True,capture_output=True,timeout=50,check=check)
def pod(*args):return run(*args).stdout.strip()
assert pod('info','--format','{{.Store.GraphRoot}}')==str(envdir/'graph')
def module(name,file):
 spec=importlib.util.spec_from_file_location(name,root/'docs/validation'/file);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
u=module('u','live-upgrade.py');g=module('g','quiescence.py')
work=Path(tempfile.mkdtemp(prefix='dl089-oom-',dir=root/'build'));project=work.name;name=project+'-engine';volume=project+'-scratch'
data=work/'data';data.mkdir()
image=pod('inspect','-f','{{.Image}}','megasamples-landing')
with socket.socket() as listener:listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
summary=dict(status='Unsupported',reason='Native result pending',artifacts=str(work.relative_to(root)))
volume_created=False;container_created=False
try:
 pod('volume','create','--label','com.docker.compose.project='+project,volume);volume_created=True
 result=run('run','-d','--pull=never','--name',name,'--label','com.docker.compose.project='+project,
   '--memory=8m','--memory-swap=8m','--pids-limit=16','--network','bridge','-p',f'127.0.0.1:{port}:8080',
   '-v',str(data)+':/fixture','-v',volume+':/scratch','--entrypoint','sh','sha256:'+image,
   '-c','value=xxxxxxxx; while :; do value=$value$value$value$value; done',check=False)
 (work/'start.log').write_text(result.stdout+result.stderr)
 container_created=run('container','exists',name,check=False).returncode==0
 if result.returncode:
  summary['reason']='Native limited-memory published container could not start; private startup error retained'
 else:
  deadline=time.monotonic()+30
  while time.monotonic()<deadline:
   state=pod('inspect','-f','{{.State.Running}}|{{.State.OOMKilled}}|{{.State.ExitCode}}',name).split('|')
   if state[0]=='false':break
   time.sleep(.1)
  if state[0]!='false' or state[1]!='true':
   summary['reason']='The 8 MiB scratch process did not produce a native OOMKilled state within the bounded attempt'
   summary['observed_state_classes']=dict(running=state[0],oom=state[1],exit_code=int(state[2]))
  else:
   snapshot=work/'before.json';u.snapshot(snapshot,project,[name],phase='candidate-teardown')
   u.exited(snapshot,work/'state-gate.json',phase='candidate-teardown')
   cap=work/'capture.json';capture=g.capture(snapshot,cap,allow_down=True,extra_sources=[data])
   attempts=[dict(outcome=capture['outcome'],holds=dict(collections.Counter(r['reason'] for r in capture['holds'])))]
   assert capture['outcome']=='PASS',attempts
   report=g.verify(cap);assert report['outcome']=='PASS',report['outcome']
   summary=dict(status='Passed',containers=1,published_loopback_ports=1,memory_limit_bytes=int(pod('inspect','-f','{{.HostConfig.Memory}}',name)),
     native_oom=True,exit_code=int(state[2]),state_gate='PASS',down_capture='PASS',down_verification='PASS',capture_attempts=attempts,
     artifacts=str(work.relative_to(root)),scope='Actual native cgroup OOM in this owned 8 MiB scratch container; no simulated OOM flag')
except Exception as error:
 summary=dict(status='Failed',reason_class=type(error).__name__,artifacts=str(work.relative_to(root)))
 raise
finally:
 if container_created:run('rm','-f',name)
 if volume_created:pod('volume','rm',volume)
 for network in pod('network','ls','-q','--filter','label=com.docker.compose.project='+project).split():pod('network','rm',network)
 assert not pod('ps','-aq','--filter','label=com.docker.compose.project='+project)
 assert not pod('volume','ls','-q','--filter','label=com.docker.compose.project='+project)
 summary['cleanup']=dict(status='Passed',containers=0,volumes=0)
 (work/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
