"""Offline-only strict-v2 validation registration over a fixed tiny source cohort.

Reuses paired_runner execution/accounting/receipts. Not a live study entry point.
"""
from copy import deepcopy
from pathlib import Path
import hashlib,json
import temporal_validation_v2 as strict
import paired_runner as paired
import tier_a_contract as contract
from tier_a_input_view import derive,RAW_FRAGMENT,VIEW_FRAGMENT
from solver_interface import require,digest,LIMITS
from offline_provider_example import OfflineTranslator

VERSION='strict-temporal-offline-consumer-v1'
ROOT=Path(__file__).resolve().parent
DIRECTORY=ROOT/'fixtures/tier-a-original-synthetic-v1'
INVALID='schema-invalid-empty-mappings'
KEYS=('optional-omitted-','optional-forced-','fragmented-3-')


def pins():
    result=paired.source_pins()
    for name in ['strict_benchmark_v1.py','temporal_validation_v2.py','tools/run_strict_benchmark.py','surgerybench/temporal_text.py','surgerybench/temporal_oracle.py','surgerybench/tier_a_audit.py']:
        result[name]=hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
    return result


def prepare_case(case_id,family,label,stratum,instance):
    errors=strict.schema_errors(instance)
    result=dict(case_id=case_id,family=family,label=label,stratum=stratum,
                instance=deepcopy(instance),input_errors=errors,text=None)
    if not errors:
        normalized=strict.normalize_instance(instance)
        canonical_text=strict.render(normalized)
        text=derive(canonical_text)
        require(strict.parse(text.replace(VIEW_FRAGMENT,RAW_FRAGMENT))==normalized,'strict text semantic round-trip')
        result.update(text=text,normalized_instance_sha256=digest(normalized),text_sha256=hashlib.sha256(text.encode()).hexdigest())
    return result


def register():
    # Verify frozen files before reading private evaluator rows or emitting text.
    for name,want in contract.HASHES.items():
        p=DIRECTORY/name
        require(p.is_file() and not p.is_symlink() and p.stat().st_size<=2*1024*1024,'bounded regular source fixture')
        require(hashlib.sha256(p.read_bytes()).hexdigest()==want,'frozen fixture hash mismatch')
    source=[contract.strict_json(s) for s in (DIRECTORY/'tier-a-gold.jsonl').read_text().splitlines()]
    old_plan=dict(contract_version=contract.CONTRACT,corpus_version=contract.CORPUS,
                  case_use={g['case_id']:'validation_only' if g['certification']=='oracle_only' else 'eligible' for g in source},repetitions=1,arms=['no_tools','csp'])
    source,model=contract.preflight(DIRECTORY,old_plan)
    selected=[next(g for g in source if g['case_id'].startswith(prefix)) for prefix in KEYS]
    cases={}
    for g in selected:
        stratum='oracle_only' if g['certification']=='oracle_only' else 'certified_negative' if g['label']=='INFEASIBLE' else 'feasible'
        cases[g['case_id']]=prepare_case(g['case_id'],g['family'],g['label'],stratum,g['instance'])
        require(not cases[g['case_id']]['input_errors'],'frozen selected source must validate')
    malformed=dict(schema_version='1.1',days=1,day_minutes=1440,patients={},surgeons={},rooms={})
    cases[INVALID]=prepare_case(INVALID,'schema-boundary-probe',None,'schema_invalid',malformed)
    settings=paired.config(dict(version=paired.VERSION,provider_revision=OfflineTranslator.revision,
        case_ids=list(cases),repetitions=1,seed=0,shuffle_cases=False,order='case_then_arm',
        token_limit=12000,wall_seconds=45,tool_call_limit=1,retry_limit=0,
        spending_ceiling=1,currency='USD',solver_revision=strict.REVISION,solver_limits=LIMITS))
    slots=[dict(case_id=i,repetition=0,arm=a) for n,i in enumerate(cases)
           for a in (('no_tools','csp') if n%2==0 else ('csp','no_tools'))]
    plan=dict(version=VERSION,strict_revision=strict.REVISION,mode='fixture',config=settings,
        source_sha256=pins(),source_fixture_sha256=deepcopy(contract.HASHES),
        source_case_ids=[g['case_id'] for g in source],selected_source_ids=[g['case_id'] for g in selected],
        source_counts=dict(FEASIBLE=7,certified_INFEASIBLE=2,oracle_only_INFEASIBLE=6),
        case_bindings={i:dict(instance_sha256=digest(g['instance']),text_sha256=g.get('text_sha256'),stratum=g['stratum'],input_errors=g['input_errors']) for i,g in cases.items()},
        slots=slots,order_policy='fixed-alternating-start-arm-v1',seed_scope='no_model_generation_seed',
        optimality='not_applicable_no_agreed_objective_or_reference',
        provider_policy='offline-fixture-only-no-model-results',tool_policy='one-required-checked-CSP-call-no-retry',retention_policy=paired.retention.policy())
    plan['run_id']=digest(plan)
    for slot in plan['slots']:slot['attempt_id']=digest(dict(run_id=plan['run_id'],slot=slot))
    return plan,cases


class StrictSolver:
    revision=strict.REVISION
    schema_version='1.1'
    supported_limits=LIMITS
    def invoke(self,arguments):
        return strict.CSPAdapter().invoke(arguments)


def summarize(plan,cases,receipts):
    current,current_cases=register()
    require(plan==current and digest(cases)==digest(current_cases),'strict registration/source/case drift')
    require(all(not cases[r['case_id']]['input_errors'] for r in receipts),'rejected input cannot have execution receipt')
    result=paired.summarize(plan,cases,receipts)
    indexed={r['attempt_id']:r for r in receipts}
    for row in result['rows']:
        g=cases[row['case_id']];r=indexed.get(row['attempt_id'])
        row.update(input_invalid=bool(g['input_errors']),stratum=g['stratum'],strict_evidence_valid=False,
                   translation_invalid=False,solver_unknown=False,format_valid=False,required_tool_missing=False,optimality='not_applicable')
        if row['input_invalid']:stage='input_schema_invalid'
        elif r is None:stage='missing'
        else:
            row['format_valid']=paired.well_formed(r)
            row['required_tool_missing']=row['arm']=='csp' and len(r['tool_calls'])!=1
            row['operational_error']|=row['required_tool_missing']
            row['success']&=not row['required_tool_missing']
            verdict=strict.score(dict(instance=g['instance'],label=g['label']),r['normalized_output'])
            row['strict_evidence_valid']=verdict['valid']
            require(not row['evidence_success'] or verdict['valid'],'independent intended-instance score conflict')
            row['translation_invalid']=any(type(t.get('arguments')) is not dict or set(t['arguments'])!={'instance'} or bool(strict.schema_errors(t['arguments']['instance'])) for t in r['tool_calls'])
            row['solver_unknown']=any(e.get('result',{}).get('status')=='UNKNOWN' and not e.get('error') for e in r['solver_events'])
            stage='timeout' if row['timeout'] else 'translation_invalid' if row['translation_invalid'] else 'provider_error' if r['provider_error'] else 'solver_error' if r['tool_error'] else 'final_invalid' if not row['format_valid'] else 'required_tool_missing' if row['required_tool_missing'] else 'usage_unknown' if row['budget_unknown'] else 'solver_unknown' if row['solver_unknown'] else 'final_unknown' if row['unknown'] else 'final_evidence_valid' if row['evidence_success'] else 'final_evidence_invalid'
        row['stage']=stage
    fields=['format_valid','required_tool_missing','input_invalid','answer_complete','evidence_success','success','unknown','output_error','timeout','translation_invalid','solver_unknown']
    result['validation_strata']={s:dict(planned=len(rows),**{k:sum(bool(r[k]) for r in rows) for k in fields},valid_missing=sum(r['missing'] and not r['input_invalid'] for r in rows)) for s in sorted({r['stratum'] for r in result['rows']}) for rows in [[r for r in result['rows'] if r['stratum']==s]]}
    for arm in result['by_arm']:
        rows=[r for r in result['rows'] if r['arm']==arm]
        result['by_arm'][arm].update(**{k:sum(r[k] for r in rows) for k in ['format_valid','required_tool_missing','translation_invalid','solver_unknown']})
        result['by_arm'][arm].update(input_invalid=sum(r['input_invalid'] for r in rows),valid_missing=sum(r['missing'] and not r['input_invalid'] for r in rows))
    def refresh(group,rows):
        for key in ['success','operational_error']:
            group[key]=sum(r[key] for r in rows)
        group['feasible_success']=sum(r['success'] and r['label']=='FEASIBLE' for r in rows)
        group['negative_success']=sum(r['success'] and r['label']=='INFEASIBLE' for r in rows)
    for arm,group in result['by_arm'].items():refresh(group,[r for r in result['rows'] if r['arm']==arm])
    for family,arms in result['by_family'].items():
        for arm,group in arms.items():refresh(group,[r for r in result['rows'] if r['family']==family and r['arm']==arm])
    pairs=dict(both=0,no_tools_only=0,csp_only=0,neither=0,incomplete=0)
    for case_id in cases:
        a,b=(next(r for r in result['rows'] if r['case_id']==case_id and r['arm']==arm) for arm in ['no_tools','csp'])
        key='incomplete' if not a['answer_complete'] or not b['answer_complete'] else 'both' if a['success'] and b['success'] else 'no_tools_only' if a['success'] else 'csp_only' if b['success'] else 'neither'
        pairs[key]+=1
    result['pairs']=pairs
    result.update(version=VERSION,status='offline_validation_only_not_model_results',
        valid_missing=sum(r['missing'] and not r['input_invalid'] for r in result['rows']),
        strict_revision=strict.REVISION,optimality=plan['optimality'])
    return result


def run(directory,provider_factory=OfflineTranslator,*,max_attempts=None):
    plan,cases=register();require(max_attempts is None or type(max_attempts) is int and 0<=max_attempts<=8,'bounded offline interruption point')
    out=Path(directory);out.mkdir(mode=0o700)
    (out/'plan.json').write_text(contract.canonical(plan)+'\n')
    receipts=[];stopped=None
    with (out/'attempts.jsonl').open('x') as stream:
        for slot in plan['slots']:
            if cases[slot['case_id']]['input_errors']:continue
            if max_attempts is not None and len(receipts)>=max_attempts:stopped='offline_interruption';break
            costs=paired.cost_summary(receipts)
            if receipts and costs['cost_usd'] is None:stopped='unknown_cost_stopped_new_slots';break
            if costs['known_cost_usd']>=plan['config']['spending_ceiling']:stopped='spending_ceiling_stopped_new_slots';break
            config=deepcopy(plan['config']);config['_spending_remaining']=config['spending_ceiling']-costs['known_cost_usd']
            row=paired.attempt(cases[slot['case_id']],slot,config,provider_factory,StrictSolver)
            row,line=paired.retention.retain(out,row);stream.write(line);stream.flush();receipts.append(row)
            if row['resource_error']:stopped='resource_bound_stopped_new_slots';break
    result=summarize(plan,cases,receipts);result['stop_reason']=stopped
    (out/'summary.json').write_text(contract.canonical(result)+'\n')
    return result


def assess(directory):
    out=Path(directory);require((out/'plan.json').stat().st_size<=4*1024*1024,'bounded plan')
    plan=contract.strict_json((out/'plan.json').read_text());current,cases=register()
    require(plan==current,'saved strict registration drift')
    receipts=paired.retention.read(out,len(plan['slots']))
    result=summarize(plan,cases,receipts)
    result['stop_reason']='resource_bound_stopped_new_slots' if any(r['resource_error'] for r in receipts) else 'unknown_cost_stopped_new_slots' if receipts and paired.cost_summary(receipts)['cost_usd'] is None else 'spending_ceiling_stopped_new_slots' if result['valid_missing'] and paired.cost_summary(receipts)['known_cost_usd']>=plan['config']['spending_ceiling'] else 'offline_interruption' if result['valid_missing'] else None
    # Assessment derives outcomes from immutable plan and receipts, never saved labels.
    return result
