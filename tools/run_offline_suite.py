"""Portable offline entry point: no network, one worker, no external pilot fixtures."""
from pathlib import Path
import runpy,sys,socket,os
ROOT=Path(__file__).resolve().parents[1]
def no_network(*args,**kwargs):raise AssertionError('network forbidden in offline tests')
socket.create_connection=no_network
socket.socket.connect=no_network
socket.socket.connect_ex=no_network
def audit(event,args):
 if event!='open' or not args or not isinstance(args[0],(str,bytes,os.PathLike)):return
 p=Path(os.fsdecode(args[0])).resolve()
 external=Path('/home/t/tehxa/cs3263-review')
 if p.is_relative_to(external) and not p.is_relative_to(ROOT) and not p.is_relative_to(Path(sys.prefix).resolve()):raise AssertionError('external xlogin fixture read forbidden: '+str(p))
sys.addaudithook(audit)
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
os.chdir(ROOT);sys.argv=[str(ROOT/'tools/run_offline_tests.py'),*sys.argv[1:]]
if '--verify-package' in sys.argv:
 sys.argv=['scripts.verify_package'];runpy.run_module('scripts.verify_package',run_name='__main__')
else:runpy.run_path(str(ROOT/'tools/run_offline_tests.py'),run_name='__main__')
