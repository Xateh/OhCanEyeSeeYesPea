"""Deterministic controlled-text fixture translator, NOT an LLM or a model baseline."""
import json
from copy import deepcopy
from tier_a_input_view import RAW_FRAGMENT,VIEW_FRAGMENT
from surgerybench.temporal_text import parse
from hard_corpus_registration import EXAMPLE,DESCRIPTION
class OfflineTranslator:
 offline=True
 revision='offline-controlled-text-example-v1'
 def respond(self,messages,tools,limits):
  # No IDs, intended instances, gold, eligibility, or run metadata enter this method.
  usage=dict(input_tokens=0,output_tokens=0,cost_usd=0) # Explicitly no model calls.
  if not tools:return dict(type='final',raw='{"status":"UNKNOWN"}',usage=usage)
  if messages[-1]['role']=='tool':
   result=json.loads(messages[-1]['content']);output={k:v for k,v in result.items() if k in ('status','schedule','certificate')}
   return dict(type='final',raw=json.dumps(output),usage=usage)
  text=messages[1]['content'].replace(VIEW_FRAGMENT,RAW_FRAGMENT)
  text=text.replace(DESCRIPTION,EXAMPLE).replace('["FIRST_ID","SECOND_ID"]','["A","E"]')
  return dict(type='tool_call',name='csp',arguments={'instance':parse(text)},usage=usage)
