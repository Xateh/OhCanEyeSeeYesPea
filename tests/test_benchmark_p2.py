from pathlib import Path
from unittest.mock import patch
import unittest,tempfile,importlib,http.client,io
import paired_runner as paired
import development_suites_audit as audit
import test_paired_runner as fixture

TRANSPORTS=['responses_transport','responses_phase_transport','responses_structured_transport','responses_astra_transport','responses_calibration_transport']
KEY='synthetic-not-a-real-key'

class Response:
    status=200
    headers={'x-request-id':'synthetic-request'}
    def __init__(self,chunks):self.chunks=iter(chunks)
    def __enter__(self):return self
    def __exit__(self,*a):pass
    def read1(self,n):
        value=next(self.chunks,b'')
        if isinstance(value,Exception):raise value
        return value
    def read(self,n):
        out=b''
        while len(out)<n:
            piece=self.read1(n-len(out))
            if not piece:return out
            out+=piece
        return out

class CostTests(unittest.TestCase):
    def test_all_missing_cost_is_unknown_per_planned_arm(self):
        plan,cases=paired.make_plan(fixture.spec(),fixture.config())
        result=paired.summarize(plan,cases,[])
        for arm in ['no_tools','csp']:
            self.assertIsNone(result['by_arm'][arm]['cost_usd'])
            self.assertEqual(result['by_arm'][arm]['known_cost_usd'],0)
            self.assertEqual(result['by_arm'][arm]['cost_coverage'],[0,1])

    def test_missing_slot_preserves_received_subtotal(self):
        config=fixture.config();config['repetitions']=2;spec=fixture.spec();spec[0]['plan']['repetitions']=2
        plan,cases=paired.make_plan(spec,config)
        receipt=paired.attempt(cases[plan['slots'][0]['case_id']],plan['slots'][0],config,fixture.Fixture,fixture.MergedSolver)
        result=paired.summarize(plan,cases,[receipt])
        arm=receipt['arm'];self.assertIsNone(result['by_arm'][arm]['cost_usd']);self.assertEqual(result['by_arm'][arm]['cost_coverage'],[1,2])

class FileBoundTests(unittest.TestCase):
    def reject_before_read(self,kind):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp)/'package';d.mkdir()
            for n in audit.FILES|{'manifest.json'}:(d/n).write_text('{}')
            target=d/'gold.jsonl'
            if kind=='oversize':
                with target.open('wb') as f:f.truncate(2*1024*1024+1)
            elif kind=='symlink':
                outside=Path(tmp)/'outside';outside.write_text('synthetic');target.unlink();target.symlink_to(outside)
            elif kind=='directory':target.unlink();target.mkdir()
            reads=[];original=audit.os.read
            def read(fd,n):reads.append((fd,n));return original(fd,n)
            with patch.object(audit.os,'read',read):
                with self.assertRaises(ValueError):audit.audit(d)
            self.assertEqual(reads,[])
    def test_oversize_rejected_before_payload_read(self):self.reject_before_read('oversize')
    def test_symlink_rejected_before_payload_read(self):self.reject_before_read('symlink')
    def test_directory_rejected_before_payload_read(self):self.reject_before_read('directory')

class RawHTTPTests(unittest.TestCase):
    def invoke(self,name,chunks):
        module=importlib.import_module(name);calls=[]
        class Opener:
            def open(self,*a,**k):calls.append(1);return Response(chunks)
        with patch('urllib.request.build_opener',return_value=Opener()):result=module.http_once({},2,KEY)
        self.assertEqual(len(calls),1);return result
    def test_truncated_key_prefix_is_redacted_in_all_legacy_transports(self):
        for name in TRANSPORTS:
            with self.subTest(transport=name):
                r=self.invoke(name,[http.client.IncompleteRead(b'{"echo":"'+KEY[:14].encode())])
                self.assertFalse(r[3]);self.assertNotIn(KEY[:14].encode(),r[2]);self.assertTrue(r[4])
    def test_read_timeout_keeps_received_chunks_without_retry(self):
        for name in TRANSPORTS:
            with self.subTest(transport=name):
                r=self.invoke(name,[b'{"partial":',TimeoutError('synthetic read timeout')])
                self.assertEqual(r[2],b'{"partial":');self.assertFalse(r[3]);self.assertEqual(r[5]['read_error'],'timeout')
    def test_protocol_failure_keeps_received_chunks_without_retry(self):
        for name in TRANSPORTS:
            with self.subTest(transport=name):
                r=self.invoke(name,[b'{"partial":',OSError('synthetic read error')])
                self.assertEqual(r[2],b'{"partial":');self.assertFalse(r[3]);self.assertEqual(r[5]['read_error'],'read_failure')


    def test_adapter_partial_receipts_reassess_as_unknown_usage_and_timeout(self):
        for name in TRANSPORTS:
            module=importlib.import_module(name)
            rates=dict(input_per_million=2,cached_input_per_million=.1,output_per_million=10,source='synthetic')
            if name in ['responses_astra_transport','responses_calibration_transport']:rates.update(cache_write_30m_per_million=2.5,cache_write_12h_per_million=5)
            binding=module.binding('mock-model','mock-model','mock-responses-v1','low',100,2,1,rates)
            for failure,chunk in [(TimeoutError,b'{"usage":{}}'),(OSError,b'{"partial":'),(TimeoutError,b'\xff')]:
                with self.subTest(transport=name,failure=failure,chunk=chunk):
                    calls=[]
                    def send(body,timeout):calls.append(1);return self.invoke(name,[chunk,failure('synthetic diagnostic')])
                    adapter=module.ResponsesAdapter(binding,transport=send)
                    with self.assertRaises(TimeoutError if failure is TimeoutError else ValueError):
                        adapter.respond([{'role':'system','content':'shared'},{'role':'user','content':'same case'}],[],dict(token_limit=1000,wall_seconds=2,spending_remaining_usd=1))
                    self.assertEqual(len(calls),1);record=adapter.calls[0]
                    self.assertFalse(record['response_complete']);self.assertIsNone(record['observed_usage'])
                    self.assertEqual(record['http_read_error'],'timeout' if failure is TimeoutError else 'read_failure')
                    if chunk!=b'\xff':self.assertEqual(record['raw_response'],chunk.decode())
                    else:self.assertEqual(record['raw_response_base64'],'/w==')
                    module.validate_record(record,binding)
                    bad=dict(record,response_complete=True)
                    with self.assertRaises(ValueError):module.validate_record(bad,binding)

    def test_complete_raw_body_and_partial_echo_boundaries(self):
        for name in TRANSPORTS:
            with self.subTest(transport=name):
                r=self.invoke(name,[b'{"ok":',b'true}',b''])
                self.assertEqual(r[2],b'{"ok":true}');self.assertTrue(r[3]);self.assertFalse(r[4])
                r=self.invoke(name,[b'{"echo":"'+KEY.encode(),TimeoutError('synthetic')])
                self.assertNotIn(KEY.encode(),r[2]);self.assertTrue(r[4])

class AdditionalCostTests(unittest.TestCase):
    def test_planned_cost_coverage_keeps_known_amount_and_rejects_bad_denominator(self):
        from study.accounting import cost_summary
        row={'call_accounting':[{'usage':{'cost_usd':.25}}]}
        value=cost_summary([row],planned_runs=2)
        self.assertIsNone(value['cost_usd']);self.assertEqual(value['known_cost_usd'],.25);self.assertEqual(value['cost_coverage'],[1,2])
        self.assertEqual(cost_summary([row],planned_runs=1)['cost_usd'],.25)
        for invalid in [0,False,1.5]:
            with self.assertRaises(ValueError):cost_summary([row],planned_runs=invalid)


class CopiedRunnerCostTests(unittest.TestCase):
    def test_missing_planned_cost_in_all_legacy_runner_summaries(self):
        import test_responses_calibration as calibration
        import test_responses_runner as helpers
        for name in ['responses_runner','responses_mandatory_runner','responses_phase_runner','responses_structured_runner','responses_astra_runner','responses_calibration_runner','responses_handoff_runner']:
            r=importlib.import_module(name);api=importlib.import_module('responses_transport' if name in ['responses_runner','responses_mandatory_runner'] else 'responses_calibration_transport' if name=='responses_handoff_runner' else name.replace('_runner','_transport'))
            if name in ['responses_calibration_runner','responses_handoff_runner']:
                c=calibration.config();specs=calibration.specs()
            else:
                c=helpers.config([fixture.cid('optional-forced'),fixture.cid('pair-deadline')]);specs=fixture.spec()
            rates=dict(input_per_million=2,cached_input_per_million=.1,output_per_million=10,source='synthetic')
            if name in ['responses_astra_runner','responses_calibration_runner','responses_handoff_runner']:rates.update(cache_write_30m_per_million=2.5,cache_write_12h_per_million=5)
            c.update(version=r.VERSION,provider_revision=api.VERSION,execution_mode='responses_mock',provider_binding=api.binding('mock-model','mock-model','mock-responses-v1','low',100,2,1,rates),tool_call_limit=1)
            with self.subTest(runner=name):
                plan,cases=r.make_plan(specs,c);result=r.summarize(plan,cases,[])
                for arm in ['no_tools','csp']:
                    self.assertIsNone(result['by_arm'][arm]['cost_estimate_usd'])
                    self.assertEqual(result['by_arm'][arm]['cost_estimate_coverage'],[0,result['by_arm'][arm]['planned']])


class RealHTTPFramingTests(unittest.TestCase):
    def response(self,body,declared=None,chunked=False):
        class Sock:
            def makefile(self,*a,**k):return io.BytesIO(wire)
        header=b'Transfer-Encoding: chunked' if chunked else b'Content-Length: '+str(len(body) if declared is None else declared).encode()
        wire=b'HTTP/1.1 200 OK\r\n'+header+b'\r\n\r\n'+body
        response=http.client.HTTPResponse(Sock());response.begin();return response
    def invoke(self,module,response):
        seen=[]
        class Opener:
            def open(self,*a,**k):seen.append(1);return response
        with patch('urllib.request.build_opener',return_value=Opener()):result=module.http_once({},2,KEY)
        self.assertEqual(len(seen),1);return result
    def test_real_short_content_length_redacts_boundary_key_prefix(self):
        for name in TRANSPORTS:
            with self.subTest(transport=name):
                body=b'{"echo":"'+KEY[:14].encode();response=self.response(body,len(body)+10)
                result=self.invoke(importlib.import_module(name),response)
                self.assertFalse(result[3]);self.assertEqual(result[5]['read_error'],'read_failure')
                self.assertNotIn(KEY[:14].encode(),result[2]);self.assertTrue(result[4])
    def test_real_complete_looking_short_body_never_scores_or_prices(self):
        import json
        envelope=dict(model='mock-model',status='completed',service_tier='default',output=[dict(type='message',role='assistant',content=[dict(type='output_text',text='{"type":"final","output":{"status":"UNKNOWN"}}')])],usage=dict(input_tokens=1,output_tokens=1,total_tokens=2,input_tokens_details=dict(cached_tokens=0,cache_write_tokens=0),output_tokens_details=dict(reasoning_tokens=0)))
        body=json.dumps(envelope).encode()
        for name in TRANSPORTS:
            with self.subTest(transport=name):
                module=importlib.import_module(name);rates=dict(input_per_million=2,cached_input_per_million=.1,output_per_million=10,source='synthetic')
                if name in ['responses_astra_transport','responses_calibration_transport']:rates.update(cache_write_30m_per_million=2.5,cache_write_12h_per_million=5)
                binding=module.binding('mock-model','mock-model','mock-responses-v1','low',100,2,1,rates)
                def send(*a):return self.invoke(module,self.response(body,len(body)+1))
                adapter=module.ResponsesAdapter(binding,transport=send)
                with self.assertRaises(ValueError):adapter.respond([{'role':'system','content':'shared'},{'role':'user','content':'same case'}],[],dict(token_limit=1000,wall_seconds=2,spending_remaining_usd=1))
                record=adapter.calls[0];self.assertFalse(record['response_complete']);self.assertIsNone(record['observed_usage']);self.assertIsNone(record['raw_model_text']);self.assertEqual(record['raw_response'],body.decode());module.validate_record(record,binding)
    def test_real_chunked_completion_and_missing_terminator(self):
        module=importlib.import_module('responses_transport')
        for wire,complete in [(b'2\r\n{}\r\n0\r\n\r\n',True),(b'2\r\n{}\r\n',False),(b'4\r\n{}',False)]:
            with self.subTest(wire=wire):
                result=self.invoke(module,self.response(wire,chunked=True));self.assertIs(result[3],complete);self.assertEqual(result[2],b'{}')
        self.assertTrue(self.invoke(module,self.response(b'{}'))[3])

class DescriptorBoundTests(unittest.TestCase):
    def package(self,d):
        names={'coverage.json','manifest.json'}
        for name in names:(d/name).write_bytes(b'{}')
        return names
    def test_actual_read_spy_observes_valid_reads(self):
        with tempfile.TemporaryDirectory() as td:
            d=Path(td);names=self.package(d);seen=[];original=audit.os.read
            def read(fd,n):seen.append(n);return original(fd,n)
            with patch.object(audit.os,'read',read):result=audit._read_blobs(d,names,16)
            self.assertTrue(seen);self.assertEqual(set(result.values()),{b'{}'})
    def test_replacement_before_open_rejected_without_read(self):
        with tempfile.TemporaryDirectory() as td:
            d=Path(td);names=self.package(d);outside=d.parent/(d.name+'-outside');outside.write_bytes(b'outside')
            original=audit.os.open;reads=[]
            def opened(path,*a,**k):
                if path=='coverage.json':(d/path).unlink();(d/path).symlink_to(outside)
                return original(path,*a,**k)
            try:
                with patch.object(audit.os,'open',opened),patch.object(audit.os,'read',side_effect=lambda *a:reads.append(a)):
                    with self.assertRaises(OSError):audit._read_blobs(d,names,16)
                self.assertEqual(reads,[])
            finally:outside.unlink()
    def test_replacement_after_open_reads_pinned_inode(self):
        with tempfile.TemporaryDirectory() as td:
            d=Path(td);names=self.package(d);outside=d.parent/(d.name+'-outside');outside.write_bytes(b'outside')
            original=audit.os.open
            def opened(path,*a,**k):
                fd=original(path,*a,**k)
                if path=='coverage.json':(d/path).unlink();(d/path).symlink_to(outside)
                return fd
            try:
                with patch.object(audit.os,'open',opened):result=audit._read_blobs(d,names,16)
                self.assertEqual(result['coverage.json'],b'{}')
            finally:outside.unlink()
    def test_growth_before_open_rejected_without_read(self):
        with tempfile.TemporaryDirectory() as td:
            d=Path(td);names=self.package(d);original=audit.os.open;reads=[]
            def opened(path,*a,**k):
                if path=='coverage.json':(d/path).write_bytes(b'x'*17)
                return original(path,*a,**k)
            with patch.object(audit.os,'open',opened),patch.object(audit.os,'read',side_effect=lambda *a:reads.append(a)):
                with self.assertRaises(ValueError):audit._read_blobs(d,names,16)
            self.assertEqual(reads,[])
    def test_growth_after_fstat_stays_bounded(self):
        with tempfile.TemporaryDirectory() as td:
            d=Path(td);names=self.package(d);original=audit.os.read;seen=[]
            def read(fd,n):
                if not seen:(d/'coverage.json').write_bytes(b'x'*21)
                value=original(fd,n);seen.append((n,len(value)));return value
            with patch.object(audit.os,'read',read):
                with self.assertRaises(ValueError):audit._read_blobs(d,names,16)
            self.assertEqual(sum(size for _,size in seen),17);self.assertTrue(all(n<=17 for n,_ in seen))
