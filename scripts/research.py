"""Portable finite comment research CLI. Offline commands need only Python 3.12."""
import argparse,csv,hashlib,json,os,shutil,subprocess,sys,re
from urllib.parse import urlparse
from pathlib import Path
from sampler import sample_unit
ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,x):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def inputs_digest(p):
 return {f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted((p/'inputs').glob('*.json'))}
def validate_plan(p):
 plan=read(p/'inputs/plan.json');cases={c['event_id'] for c in plan['cases']};ids=set()
 domains={'BILI':'bilibili.com','DY':'douyin.com','WB':'weibo.com','XHS':'xiaohongshu.com'}
 for u in plan['units']:
  if not re.fullmatch(r'[A-Za-z0-9_-]+',u['unit_id']) or u['unit_id'] in ids:raise ValueError('任务ID非法或重复')
  ids.add(u['unit_id'])
  if u['event_id'] not in cases or u['platform'] not in domains:raise ValueError('任务案例/平台不在计划内')
  if not any(v['event_id']==u['event_id'] and v['platform']==u['platform'] and v['video_id']==u['video_id'] for v in plan['videos']):raise ValueError('视频未登记')
  url=urlparse(u['url']);domain=domains[u['platform']]
  if url.scheme!='https' or not (url.hostname==domain or (url.hostname or '').endswith('.'+domain)) or url.username or url.password:raise ValueError('仅接受对应平台正常HTTPS地址')
 return plan

def freeze(p):
 dest=p/'inputs.sha256.json';current=inputs_digest(p)
 if dest.exists() and read(dest)!=current:raise SystemExit('冻结输入已改变；请新建项目版本')
 write(dest,current)
def candidates(unit):
 rows=[]
 for stream in ['H','T']:
  for i in range(1,51):
   cid=str(9000000000000000000+i);key='BILI|DEMO_VIDEO|'+cid
   rows.append(dict(unit_id=unit,event_id='DEMO',category='自定义类别',platform='BILI',video_id='DEMO_VIDEO',comment_id=cid,comment_key=key,stream=stream,stream_position=i,level=1,raw_text=('不应该处罚' if i%5==0 else '=合成文字' if i==1 else '合成评论'),time_lower=f'2025-01-{1+(i%28):02d}T12:00:00+08:00',time_upper=f'2025-01-{1+(i%28):02d}T12:00:00+08:00',scope_status='in_window',content_loaded=True,content_kind='text',sort_mode_observed='合成排序'))
 return rows
def summarize(p):
 freeze(p);plan=read(p/'inputs/plan.json');cfg=read(p/'inputs/config.json');results=[];audit=[]
 for u in plan['units']:
  f=p/'evidence'/u['unit_id']/'capture.json'
  if not f.exists():audit.append(dict(unit_id=u['unit_id'],status='missing_evidence'));continue
  cap=read(f);rows=cap.get('candidates',[])
  for r in rows:
   expected='|'.join([u['platform'],u['video_id'],str(r.get('comment_id',''))])
   if not r.get('comment_id') or str(r['comment_id']).startswith('proxy_') or r['comment_key']!=expected:raise ValueError('原生评论身份不一致')
  result=sample_unit(rows,cfg,u['unit_id']);results.append(result)
  audit.append(dict(unit_id=u['unit_id'],status=cap.get('status','unknown'),quota_log=result['quota_log'],featured_hint=cap.get('page_features',{}).get('featured'),reply_context_status='not_collected'))
 write(p/'outputs/result.json',results);write(p/'outputs/audit.json',audit)
 fields=['unit_id','comment_key','comment_id','platform','video_id','raw_text','time_lower','content_kind','sample_group']
 with (p/'outputs/comments.csv').open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
  for result in results:
   keys={m['comment_key'] for m in result['sample_memberships'] if m['layer']=='K'}
   for r in result['root_records']:
    row={k:r.get(k,'') for k in fields};row['sample_group']='K' if r['comment_key'] in keys else 'neutral'
    # Only CSV display escapes spreadsheet formula triggers. JSON is unchanged.
    row={k:("'"+v if isinstance(v,str) and v.startswith(('=','+','-','@','\t','\r')) else v) for k,v in row.items()};w.writerow(row)
 write(p/'outputs/evidence.sha256.json',{str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted((p/'evidence').glob('*/capture.json'))})
 print(json.dumps({'tasks':len(audit),'roots':sum(len(x['root_records']) for x in results)},ensure_ascii=False))
def main():
 ap=argparse.ArgumentParser();ap.add_argument('command',choices=['init','demo','login','collect','summarize','verify']);ap.add_argument('--project',type=Path,required=True);ap.add_argument('--platform',choices=['BILI','DY','XHS','WB']);ap.add_argument('--events',nargs='*');ap.add_argument('--query',type=int,choices=[1,2,3]);a=ap.parse_args();p=a.project.resolve()
 if a.command in ['init','demo']:
  if p.exists():raise SystemExit('目标已存在，拒绝覆盖')
  (p/'inputs').mkdir(parents=True)
  for f in (ROOT/'examples').glob('*.json'):shutil.copy2(f,p/'inputs'/f.name)
  if a.command=='demo':
   u='DEMO_BILI_V1';write(p/'evidence'/u/'capture.json',{'status':'synthetic','candidates':candidates(u)});summarize(p)
  return
 if a.command=='verify':
  freeze(p);expected=read(p/'outputs/evidence.sha256.json')
  for name,digest in expected.items():
   if hashlib.sha256((p/name).read_bytes()).hexdigest()!=digest:raise ValueError('证据哈希不一致')
  before=(p/'outputs/result.json').read_bytes();summarize(p)
  if before!=(p/'outputs/result.json').read_bytes():raise ValueError('抽样结果不能复现')
  print('VERIFY OK');return
 if a.command=='summarize':summarize(p);return
 if not a.platform:raise SystemExit('需要 --platform')
 if a.command=='login':
  from scrapling.fetchers import DynamicSession
  urls={'BILI':'https://www.bilibili.com','DY':'https://www.douyin.com','WB':'https://weibo.com','XHS':'https://www.xiaohongshu.com'}
  def hold(page):input('请在普通浏览器中自行登录，完成后在终端按回车：')
  with DynamicSession(user_data_dir=str(p/'.private/browser_profiles'/a.platform),headless=False,real_chrome=True,google_search=False) as session:session.fetch(urls[a.platform],page_action=hold)
  return
 validate_plan(p);freeze(p)
 cmd=[sys.executable,str(ROOT/'scripts/collect_browser.py'),a.platform]
 if a.events:cmd+=['--events']+a.events
 if a.query:cmd+=['--query',str(a.query)]
 env=dict(os.environ,COMMENT_RESEARCH_PROJECT=str(p));subprocess.run(cmd,env=env,check=True)
if __name__=='__main__':main()
