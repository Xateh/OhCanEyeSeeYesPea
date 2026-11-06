"""Versioned model-translation-only boundary; no new solver implementation."""
from copy import deepcopy
import hashlib,json,math,time
from surgerybench.temporal_check import schema_errors,check_schedule,check_certificate
from surgerybench.temporal_csp import CSPAdapter,TOOL
VERSION='checked-solver-interface-v1'
LIMITS={'max_nodes':100000,'seconds':2}
def require(ok,message):
 if not ok:raise ValueError(message)
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def limits(value):
 require(type(value) is dict and set(value)=={'max_nodes','seconds'},'explicit solver limits')
 require(type(value['max_nodes']) is int and 1<=value['max_nodes']<=100000,'solver node bound')
 n=value['seconds'];require(type(n) in (int,float) and 0<n<=2 and (type(n) is int or math.isfinite(n)),'solver seconds bound')
 return deepcopy(value)
class MergedSolver:
 revision=CSPAdapter.revision
 schema_version='1.1'
 supported_limits=LIMITS
 def __init__(self):self.adapter=CSPAdapter()
 def invoke(self,arguments):return self.adapter.invoke(arguments)
class CheckedSolver:
 tool_definition=TOOL
 def __init__(self,plugin,expected_revision,configured_limits):
  require(getattr(plugin,'revision',None)==expected_revision and type(expected_revision) is str and bool(expected_revision),'explicit solver revision')
  require(getattr(plugin,'schema_version',None)=='1.1','unsupported solver schema')
  self.limits=limits(configured_limits);require(getattr(plugin,'supported_limits',None)==self.limits,'plugin must declare exact supported limits')
  self.plugin=plugin;self.revision=expected_revision;self.events=[]
 def invoke(self,arguments):
  event={'interface_version':VERSION,'solver_revision':self.revision,'limits':deepcopy(self.limits),'error':False,'timeout':False};start=time.perf_counter()
  try:
   require(type(arguments) is dict and set(arguments)=={'instance'},'only translated instance accepted')
   instance=deepcopy(arguments['instance']);require(not schema_errors(instance),'invalid translated schema1.1')
   event['translated_instance_sha256']=digest(instance)
   result=self.plugin.invoke({'instance':deepcopy(instance)})
   require(len(json.dumps(result,sort_keys=True,allow_nan=False).encode())<=1024*1024,'solver result byte bound')
   event['raw_result']=deepcopy(result)
   require(type(result) is dict and type(result.get('status')) is str,'malformed solver result')
   status=result['status'];allowed={'status','nodes'}
   if status=='FEASIBLE':
    allowed|={'schedule'};require('schedule' in result and not check_schedule(instance,result['schedule']),'invalid translated-instance witness')
   elif status=='INFEASIBLE':
    allowed|={'certificate'};require(check_certificate(instance,result.get('certificate')),'unsupported translated-instance proof')
   elif status=='UNKNOWN':
    allowed|={'reason','search_exhausted'};require(type(result.get('reason')) is str and bool(result['reason']),'UNKNOWN reason required')
    require('search_exhausted' not in result or type(result['search_exhausted']) is bool,'exhaustion flag')
   else:raise ValueError('unsupported solver status')
   require(set(result)<=allowed,'contradictory/unsupported solver fields')
   require('nodes' not in result or type(result['nodes']) is int and 0<=result['nodes']<=self.limits['max_nodes']+1,'solver node receipt')
   output=deepcopy(result)
  except TimeoutError:
   event.update(error=True,timeout=True);output={'status':'UNKNOWN','reason':'solver_timeout'}
  except Exception as error:
   event.update(error=True,diagnostic=type(error).__name__);output={'status':'UNKNOWN','reason':'solver_contract_or_execution_error'}
  event['elapsed_seconds']=time.perf_counter()-start
  if event['elapsed_seconds']>self.limits['seconds']:
   event.update(error=True,timeout=True);output={'status':'UNKNOWN','reason':'solver_elapsed_limit'}
  event['result']=deepcopy(output);self.events.append(event);return output
