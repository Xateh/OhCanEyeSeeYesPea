"""Review-only test harness: one executor worker, forbid real Claude subprocess calls."""
import concurrent.futures
from pathlib import Path
import subprocess
import sys
import unittest
sys.path.insert(0,str(Path.cwd()))
sys.path.insert(0,str(Path.cwd()/'tests'))
original_executor=concurrent.futures.ThreadPoolExecutor
original_run=subprocess.run

def single_worker(max_workers=None,*args,**kwargs):
    return original_executor(1,*args,**kwargs)

def offline_run(argv,*args,**kwargs):
    executable=argv if isinstance(argv,str) else str(argv[0])
    if Path(executable).name=='claude':raise AssertionError('real Claude invocation forbidden in review')
    return original_run(argv,*args,**kwargs)

concurrent.futures.ThreadPoolExecutor=single_worker
subprocess.run=offline_run
pattern=sys.argv[1] if len(sys.argv)>1 else 'test_*.py'
suite=unittest.defaultTestLoader.discover('tests',pattern=pattern)
result=unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(0 if result.wasSuccessful() else 1)
