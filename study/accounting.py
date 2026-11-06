"""Retain observed CLI usage independently of answer parsing; unknown never means zero."""
from copy import deepcopy
import math
from surgerybench.temporal_benchmark import MockProvider

def known_cost(value):
    return type(value) in (int,float) and 0<=value<1_000_000_000 and (type(value) is int or math.isfinite(value))

def envelope_usage(envelope):
    if type(envelope) is not dict:return None
    usage=envelope.get('usage');usage=usage if type(usage) is dict else {}
    def token(key,default=None):
        v=usage.get(key,default)
        return v if type(v) is int and v>=0 else None
    incoming=[token('input_tokens'),token('cache_creation_input_tokens',0),token('cache_read_input_tokens',0)]
    cost=envelope.get('total_cost_usd')
    return dict(input_tokens=sum(incoming) if all(v is not None for v in incoming) else None,
                output_tokens=token('output_tokens'),cost_usd=cost if known_cost(cost) else None)

def attach(row,provider):
    if type(provider) is MockProvider:
        observations=[dict(usage=dict(input_tokens=0,output_tokens=0,cost_usd=0),reason='offline mock; no model calls')]
    else:observations=getattr(provider,'attempt_accounting',None)
    if observations is None:return row
    result=dict(row,call_accounting=deepcopy(observations))
    complete=bool(observations) and all(type(x.get('usage')) is dict and all(type(x['usage'].get(k)) is int and x['usage'][k]>=0 for k in ('input_tokens','output_tokens')) for x in observations)
    result['token_usage']={k:sum(x['usage'][k] for x in observations) for k in ('input_tokens','output_tokens')} if complete else None
    result['token_usage_reason']=None if complete else 'one or more attempted CLI calls has unknown token usage'
    return result

def observed_costs(row):
    if 'call_accounting' in row:
        calls=row['call_accounting']
        if type(calls) is not list or not calls:return [],False
        values=[x.get('usage',{}).get('cost_usd') if type(x) is dict and type(x.get('usage')) is dict else None for x in calls]
        return [v for v in values if known_cost(v)],all(known_cost(v) for v in values)
    responses=row.get('responses',[])
    values=[x.get('usage',{}).get('cost_usd') if type(x) is dict and type(x.get('usage')) is dict else None for x in responses]
    complete=bool(values) and all(known_cost(v) for v in values) and not row.get('parsing_or_provider_error',bool(row.get('errors')))
    return [v for v in values if known_cost(v)],complete

def row_cost(row):
    values,complete=observed_costs(row)
    return sum(values) if complete else None

def cost_summary(rows):
    costs=[row_cost(r) for r in rows]
    unknown=sum(c is None for c in costs)
    return dict(cost_usd=None if unknown else sum(costs),known_cost_usd=sum(sum(observed_costs(r)[0]) for r in rows),unknown_cost_runs=unknown,cost_coverage=[len(rows)-unknown,len(rows)])

def validate_budget(budget,workers):
    if type(workers) is not int or workers<1:raise ValueError('positive worker count required')
    if not known_cost(budget):raise ValueError('finite nonnegative supported scheduling budget required')
