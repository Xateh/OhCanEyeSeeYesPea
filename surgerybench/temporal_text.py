"""Controlled natural language for the bounded pilot; parser is a MOCK translator."""
import re
from .temporal_check import schema_errors

RULES = '''Schedule these surgeries. Return JSON with status FEASIBLE and schedule (rows with patient, day, start, room), INFEASIBLE and certificate, or UNKNOWN.
Use integer minutes. Days are zero-based; a schedule start is minutes after midnight. Arrival and completion deadline below are absolute minutes from the start of day 0. Start must be at or after arrival and completion must be at or before the deadline. Each mandatory surgery must occur exactly once; optional surgeries may be omitted and otherwise occur at most once. A surgery is nonpreemptive and occupies its whole duration in one room with its fixed surgeon. Intervals are half-open [start,end); adjacency is allowed when the required gap is zero. The entire interval must fit one availability window of each resource. No room or surgeon may overlap; respect each resource's required gap and daily surgery-minute budget. Use only eligible rooms. Priority and emergency flags are descriptive metadata with no additional constraints.
For an infeasible decision, a supported certificate is {"kind":"pair_order_impossible","patients":["A","E"]}: two mandatory surgeries forced to share a surgeon or a single eligible room cannot fit in either order even ignoring calendars, gaps and budgets. If no sound supported proof is known, return UNKNOWN. Do not split, interrupt, or reassign surgeons. Schema 1.1 reuses release/due as absolute-minute arrival/completion bounds; schema 1.0 day-window semantics do not apply here.'''


def render(i):
    if schema_errors(i):
        raise ValueError(schema_errors(i))
    lines = [RULES, f"The horizon has {i['days']} days of 1440 minutes."]
    for kind in ('surgeons', 'rooms'):
        noun = 'Surgeon' if kind == 'surgeons' else 'Room'
        for r in i[kind]:
            lines.append(f"{noun} {r['id']} requires a gap of {r['gap']} minutes.")
            for d in range(i['days']):
                windows = ', '.join(f'[{a},{b})' for a,b in r['calendar'][d]) or 'none'
                lines.append(f"On day {d}, {noun.lower()} {r['id']} is available during {windows}, with a surgery budget of {r['budgets'][d]} minutes.")
    for p in i['patients']:
        rooms = ', '.join(p['eligible_rooms']) or 'no eligible rooms'
        lines.append(f"Surgery {p['id']} is {'mandatory' if p['mandatory'] else 'optional'}, uses surgeon {p['surgeon']}, takes {p['duration']} minutes, arrives at minute {p['release']}, and must complete by minute {p['due']}. Eligible rooms: {rooms}. Priority: {p['priority']}. Emergency metadata: {str(p.get('emergency', False)).lower()}.")
    return '\n'.join(lines) + '\n'


def parse(text):
    if not isinstance(text, str) or not text.startswith(RULES + '\n'):
        raise ValueError('unsupported controlled language')
    lines = text[len(RULES)+1:].splitlines()
    m = re.fullmatch(r'The horizon has (\d+) days of 1440 minutes\.', lines.pop(0))
    if not m: raise ValueError('missing horizon')
    i = {'schema_version':'1.1','days':int(m[1]),'day_minutes':1440,'surgeons':[],'rooms':[],'patients':[]}
    lookup = {}
    for line in lines:
        m = re.fullmatch(r'(Surgeon|Room) (\w+) requires a gap of (\d+) minutes\.', line)
        if m:
            r = {'id':m[2],'gap':int(m[3]),'budgets':[None]*i['days'],'calendar':[None]*i['days']}
            i['surgeons' if m[1]=='Surgeon' else 'rooms'].append(r); lookup[m[1].lower(),m[2]] = r
            continue
        m = re.fullmatch(r'On day (\d+), (surgeon|room) (\w+) is available during (.+), with a surgery budget of (\d+) minutes\.', line)
        if m:
            d = int(m[1]); r = lookup[m[2],m[3]]
            r['budgets'][d] = int(m[5]); r['calendar'][d] = [[int(a),int(b)] for a,b in re.findall(r'\[(\d+),(\d+)\)',m[4])]
            continue
        m = re.fullmatch(r'Surgery (\w+) is (mandatory|optional), uses surgeon (\w+), takes (\d+) minutes, arrives at minute (\d+), and must complete by minute (\d+)\. Eligible rooms: (.+)\. Priority: (\d+)\. Emergency metadata: (true|false)\.',line)
        if not m: raise ValueError('unrecognized sentence')
        i['patients'].append({'id':m[1],'mandatory':m[2]=='mandatory','surgeon':m[3],'duration':int(m[4]),'release':int(m[5]),'due':int(m[6]),'eligible_rooms':[] if m[7]=='no eligible rooms' else m[7].split(', '),'priority':int(m[8]),'emergency':m[9]=='true'})
    if schema_errors(i) or render(i) != text: raise ValueError('invalid or noncanonical controlled language')
    return i
