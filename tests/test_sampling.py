import sys,unittest,tempfile,json,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from research import ROOT,candidates,read,freeze
from sampler import sample_unit
class SamplingTests(unittest.TestCase):
 def test_overlap_determinism_and_no_keyword_semantics(self):
  rows=candidates('DEMO_BILI_V1');cfg=read(ROOT/'examples/config.json')
  a=sample_unit(rows,cfg,'DEMO_BILI_V1');b=sample_unit(list(reversed(rows)),cfg,'DEMO_BILI_V1')
  self.assertEqual(a['sample_memberships'],b['sample_memberships']);self.assertEqual(a['baseline_members_n'],20)
  self.assertLessEqual(a['baseline_unique_n'],20)
  k={m['comment_key'] for m in a['sample_memberships'] if m['layer']=='K'};neutral={m['comment_key'] for m in a['sample_memberships'] if m['layer']!='K'};self.assertFalse(k&neutral)
  self.assertTrue(all(r['raw_text']=='不应该处罚' for r in a['root_records'] if r['comment_key'] in k))
 def test_small_pool_no_reallocation(self):
  rows=candidates('DEMO_BILI_V1')[:2];a=sample_unit(rows,read(ROOT/'examples/config.json'),'DEMO_BILI_V1');self.assertEqual(a['baseline_members_n'],2);self.assertEqual(sum(g.get('gap',0) for g in a['quota_log']),18)
 def test_image_kept_unknown_date_excluded(self):
  rows=candidates('DEMO_BILI_V1')[:2];rows[0].update(raw_text='',content_kind='image');rows[1].update(scope_status='unknown_date',time_lower=None,time_upper=None)
  a=sample_unit(rows,read(ROOT/'examples/config.json'),'DEMO_BILI_V1');self.assertEqual(a['baseline_unique_n'],1);self.assertEqual(a['root_records'][0]['content_kind'],'image')
 def test_conflicting_version_rejected(self):
  rows=candidates('DEMO_BILI_V1');rows[-1]['raw_text']='冲突版本'
  with self.assertRaises(AssertionError):sample_unit(rows,read(ROOT/'examples/config.json'),'DEMO_BILI_V1')
 def test_frozen_input_change_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'inputs').mkdir();(p/'inputs/a.json').write_text('{}');freeze(p);(p/'inputs/a.json').write_text('{"changed":true}')
   with self.assertRaises(SystemExit):freeze(p)
if __name__=='__main__':unittest.main()
