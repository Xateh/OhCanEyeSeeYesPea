"""Case-independent final syntax only; no gold, IDs or mathematical facts."""
import hashlib,json
VERSION='surgery-final-schema-v1'
def obj(properties):return dict(type='object',properties=properties,required=list(properties),additionalProperties=False)
def enum(value):return dict(type='string',enum=[value])
ROW=obj(dict(patient={'type':'string'},day={'type':'integer'},start={'type':'integer'},room={'type':'string'}))
CERT=obj(dict(kind=enum('pair_order_impossible'),patients=dict(type='array',items={'type':'string'})))
SCHEMA=obj(dict(type=enum('final'),output={'anyOf':[
 obj(dict(status=enum('FEASIBLE'),schedule=dict(type='array',items=ROW))),
 obj(dict(status=enum('INFEASIBLE'),certificate=CERT)),
 obj(dict(status=enum('UNKNOWN')))]}))
SHA256=hashlib.sha256(json.dumps(SCHEMA,sort_keys=True,separators=(',',':')).encode()).hexdigest()
FORMAT=dict(format=dict(type='json_schema',name='surgery_final_v1',strict=True,schema=SCHEMA))
def valid(value):
 if type(value) is not dict or set(value)!={'type','output'} or value['type']!='final':return False
 out=value['output']
 if type(out) is not dict:return False
 if out.get('status')=='UNKNOWN':return set(out)=={'status'}
 if out.get('status')=='FEASIBLE':
  return set(out)=={'status','schedule'} and type(out['schedule']) is list and all(type(x) is dict and set(x)=={'patient','day','start','room'} and type(x['patient']) is str and type(x['room']) is str and type(x['day']) is int and type(x['start']) is int for x in out['schedule'])
 if out.get('status')=='INFEASIBLE':
  c=out.get('certificate');return set(out)=={'status','certificate'} and type(c) is dict and set(c)=={'kind','patients'} and c['kind']=='pair_order_impossible' and type(c['patients']) is list and all(type(x) is str for x in c['patients'])
 return False
