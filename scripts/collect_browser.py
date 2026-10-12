"""正常页面有限试采；不直接请求接口，不绕过验证。"""
import json,time,re,sys,hashlib,argparse,importlib.util,logging,os
from pathlib import Path
from datetime import datetime,timezone,timedelta
from urllib.parse import quote,urlparse,parse_qs
from html import unescape
from scrapling.fetchers import DynamicSession
R=Path(os.environ.get('COMMENT_RESEARCH_PROJECT','')).resolve()
if not os.environ.get('COMMENT_RESEARCH_PROJECT'):raise SystemExit('通过 research.py collect 调用并指定 --project')
B=R;TZ=timezone(timedelta(hours=8));SNAP=R/'inputs'
profiles={k:str(R/'.private'/'browser_profiles'/k) for k in ['BILI','DY','XHS','WB']}
cfg=json.loads((SNAP/'config.json').read_text());plan=json.loads((SNAP/'plan.json').read_text());cases={e['event_id']:e for e in plan['cases']};seeds=plan['videos']
if cfg['positions_per_stream']!=50:raise SystemExit('当前浏览器适配器仅支持每流50候选位置')
logging.disable(logging.INFO) # 页面分享参数不打印；只打印净化后的任务计数。
import sampler as sample
def now():return datetime.now(TZ).isoformat()
def save(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2))
def date_bounds(value,raw):
 if isinstance(value,(int,float)):
  dt=datetime.fromtimestamp(value/1000 if value>1e12 else value,TZ);return dt.isoformat(),dt.isoformat(),'timestamp'
 if value and isinstance(value,str):
  try:dt=datetime.strptime(value,'%a %b %d %H:%M:%S %z %Y').astimezone(TZ);return dt.isoformat(),dt.isoformat(),'timestamp'
  except ValueError:pass
 m=re.search(r'(?<!\d)(\d{4}|\d{2})[-年/](\d{1,2})[-月/](\d{1,2})',raw or '')
 if m:
  year=int(m[1]);year=2000+year if year<100 else year
  dt=datetime(year,int(m[2]),int(m[3]),tzinfo=TZ);return dt.isoformat(),(dt+timedelta(days=1,microseconds=-1)).isoformat(),'day'
 return None,None,'unknown'

BILI_JS='''() => {let root=document.querySelector('bili-comments')?.shadowRoot,h=root?.querySelector('bili-comments-header-renderer')?.shadowRoot;return {sort:h?.querySelector('#sort-actions')?.className??'',rows:[...(root?.querySelectorAll('bili-comment-thread-renderer')??[])].map(t=>{let rr=t.shadowRoot?.querySelector('bili-comment-renderer'),r=rr?.shadowRoot,a=r?.querySelector('bili-comment-action-buttons-renderer')?.shadowRoot,d=t.data||t._data||rr?.data||rr?._data,rich=r?.querySelector('bili-rich-text')?.shadowRoot?.querySelector('#contents');return {id:d?.rpid_str||null,text:rich?.textContent??'',time_raw:a?.querySelector('#pubdate')?.textContent??'',timestamp:d?.ctime,likes:d?.like,actor:String(d?.member?.mid??''),has_media:!!r?.querySelector('bili-comment-pictures-renderer'),loaded:!!rich,root:d?.root_str,parent:d?.parent_str}})}}'''
DY_JS='''() => ({rows:[...document.querySelectorAll('[data-e2e="comment-item"]')].map(n=>({id:n.getAttribute('data-id')||n.getAttribute('data-comment-id'),text:n.querySelector('.FduGc_lz')?.textContent?.trim()??'',time_raw:n.querySelector('.VAQA49VP')?.textContent?.trim()??'',actor:n.querySelector('a[href*="/user/"]')?.href??'',loaded:!!n.querySelector('.FduGc_lz'),has_media:!!n.querySelector('img:not([class*="avatar"])'),visible:n.innerText?.slice(0,500)})),sort:'默认排序'})'''
WB_JS='''() => ({rows:[...document.querySelectorAll('.wbpro-scroller-item')].map(n=>{let item=n.querySelector('.item1in'),t=item?.querySelector('.con1 > .text'),s=t?.innerText??'';return {text:s.slice(s.indexOf(':')+1),time_raw:item?.querySelector('.info > div')?.innerText??'',loaded:!!t,has_media:!!t?.querySelector('img'),actor:item?.querySelector('a[href*="/u/"]')?.href??'',visible:item?.innerText?.slice(0,500)}}),sort:[...document.querySelectorAll('div.item')].filter(n=>['按热度','按时间'].includes(n.innerText)).map(n=>({text:n.innerText,cls:n.className})),featured:document.body.innerText.includes('以下为博主精选评论')})'''
XHS_JS='''() => ({rows:[...document.querySelectorAll('.parent-comment')].map(n=>({id:n.id?.replace(/^comment-/,''),text:n.querySelector('.content')?.textContent?.trim()??'',time_raw:n.querySelector('.date')?.innerText??'',loaded:!!n.querySelector('.content'),has_media:!!n.querySelector('.content img'),actor:n.querySelector('a[href*="/user/profile/"]')?.href??''})),sort:'默认排序'})'''

ap=argparse.ArgumentParser();ap.add_argument('platform',choices=list(profiles));ap.add_argument('--events',nargs='*');ap.add_argument('--query',type=int,choices=[1,2,3]);ap.add_argument('--backup-units',nargs='*',default=[]);ap.add_argument('--known-title',action='store_true',help='仅以冻结标题补充定位原ID，不选新视频');args=ap.parse_args()
from access import ensure_allowed
ensure_allowed(R,args.platform)
tasks=[u for u in plan['units'] if u['platform']==args.platform and (not args.events or u['event_id'] in args.events)]
with DynamicSession(user_data_dir=str(B/profiles[args.platform]),headless=False,real_chrome=True,google_search=False,timeout=30000) as session:
 for u in tasks:
  if u['unit_id'] in args.backup_units:
   backup_seed=next(v for v in seeds if v['event_id']==u['event_id']and v['platform']==u['platform']and v['video_id']==u['backup_video_id'])
   u=dict(u,planned_video_id=u['video_id'],planned_url=u['url'],planned_title=u['title'],replacement_reason='原视频三组正常检索及冻结标题检索均未定位，按既定规则启用同案同平台第三条一次',video_id=u['backup_video_id'],url=u['backup_url'],title=backup_seed['title'],author=backup_seed['author'],published_at=backup_seed['published_at'],frozen_public_count=backup_seed['comment_count'])
  out=R/'evidence'/u['unit_id'];out.mkdir(parents=True,exist_ok=True);dest=out/'capture.json'
  if dest.exists():raise SystemExit('已有证据，禁止覆盖；重试请建立独立项目版本')
  start=time.monotonic();state={'unit':u,'started_at':now(),'method':'正常页面加载；DOM及其正常加载响应；未直接调用接口','actions':[],'streams':{},'candidates':[],'reply_context':[]};active='H';pools={'H':{},'T':{}};sorts={'H':'默认排序','T':'未开始'};overflow={};stopped=None
  def add(x,source):
   text=x.get('text') or '';cid=str(x.get('id') or '')
   if not cid:
    state['missing_native_id_n']=state.get('missing_native_id_n',0)+1;return
   if cid in pools[active]:return
   if len(pools[active])>=50:
    if active=='H' and args.platform in ['DY','XHS'] and len(overflow)<50:overflow.setdefault(cid,(dict(x),source))
    return
   lo,hi,precision=date_bounds(x.get('timestamp'),x.get('time_raw',''))
   wlo,whi=cfg['comment_window'];scope='unknown_date' if not lo else 'in_window' if wlo<=lo<=hi<=whi else 'out_of_window'
   actor=x.get('actor','');key=u['platform']+'|'+u['video_id']+'|'+cid
   r={'unit_id':u['unit_id'],'event_id':u['event_id'],'category':u['category'],'platform':u['platform'],'video_id':u['video_id'],'stream':active,'stream_position':len(pools[active])+1,'comment_key':key,'comment_id':cid,'proxy_id':cid.startswith('proxy_'),'level':1,'raw_text':text,'time_lower':lo,'time_upper':hi,'posted_raw':x.get('time_raw',''),'date_precision':precision,'scope_status':scope,'content_loaded':bool(x.get('loaded',True)),'content_kind':'text' if text else 'image' if x.get('has_media') else 'technical_missing','sort_mode_observed':sorts[active],'likes':x.get('likes'),'source_url':u['url'],'captured_at':now(),'evidence_source':source}
   pools[active][cid]=r
  def response(resp):
   nonlocal_dummy=None
   if args.platform=='BILI':return
   path=urlparse(resp.url).path;query=parse_qs(urlparse(resp.url).query)
   try:
    if args.platform=='DY' and '/comment/list/' in path and '/reply' not in path:
     if query.get('aweme_id',[''])[0]!=u['video_id']:return
     j=resp.json();rows=j.get('comments',[]) or []
     for a in rows:
      add({'id':a.get('cid'),'text':a.get('text',''),'timestamp':a.get('create_time'),'time_raw':str(a.get('create_time','')),'likes':a.get('digg_count'),'actor':str((a.get('user')or{}).get('uid','')),'has_media':bool(a.get('image_list'))},path)
    elif args.platform=='WB' and ('/build_comments' in path or '/buildComments' in path):
     
     if not u.get('native_post_id') or query.get('id',[''])[0]!=str(u['native_post_id']):return
     j=resp.json();rows=j.get('data',[]) or []
     if isinstance(rows,list):
      for a in rows:add({'id':a.get('idstr') or a.get('id'),'text':a.get('text_raw',a.get('text','')),'timestamp':a.get('created_at'),'time_raw':a.get('created_at',''),'likes':a.get('like_counts'),'actor':str((a.get('user')or{}).get('idstr',(a.get('user')or{}).get('id','')))},path)
    elif args.platform=='XHS' and '/comment/page' in path:
     if query.get('note_id',[''])[0]!=u['video_id']:return
     j=resp.json();rows=(j.get('data')or{}).get('comments',[]) or []
     for a in rows:add({'id':a.get('id'),'text':a.get('content',''),'timestamp':a.get('create_time'),'time_raw':str(a.get('create_time','')),'likes':a.get('like_count'),'actor':str((a.get('user_info')or{}).get('user_id','')),'has_media':bool(a.get('pictures'))},path)
   except Exception as ex:state['actions'].append({'time':now(),'action':'响应解析失败','path':path,'error_type':type(ex).__name__})
  def setup(page):page.on('response',response)
  def block(page):
   global stopped
   text=page.locator('body').inner_text();title=page.title()
   if any(s in text for s in ['访问频次过高','操作频繁','搜索过于频繁']):return 'rate_limited'
   if '/captcha' in page.url or '验证码' in title or '安全验证' in title or any(s in text for s in ['请完成下方验证','拖动滑块','请完成安全验证']):return 'captcha'
   if '登录后查看搜索结果' in text or 'passport.weibo' in page.url:return 'login_required'
   return None
  def scan(page,stream,continuation=False):
   global active,stopped
   active=stream;history=[];no_new=0;previous_count=-1
   for step in range(45):
    if time.monotonic()-start>480:stopped='time_budget';break
    stopped=block(page)
    if stopped:break
    before=len(pools[stream]);snap=page.evaluate({'BILI':BILI_JS,'DY':DY_JS,'WB':WB_JS,'XHS':XHS_JS}[args.platform])
    if args.platform=='BILI':
     for x in snap['rows']:add(x,'页面DOM及组件公开评论数据')
    elif False:
     for x in snap['rows'][:50]:add(x,'页面DOM代理身份')
    state['page_features']=dict(sort=snap.get('sort'),featured=snap.get('featured'))
    history.append({'step':step,'positions':len(pools[stream]),'time':now()})
    if len(pools[stream])>=50:break
    no_new=no_new+1 if len(pools[stream])==previous_count else 0
    previous_count=len(pools[stream])
    if no_new>=2:stopped='two_loads_without_new_positions';break
    if args.platform=='BILI':page.evaluate('''() => {let a=[...(document.querySelector('bili-comments')?.shadowRoot?.querySelectorAll('bili-comment-thread-renderer')??[])];a.at(-1)?.scrollIntoView({block:'end'})}''')
    elif args.platform=='DY':
     try:page.locator('[data-e2e="comment-item"]').last.hover(timeout=3000)
     except Exception:pass
     page.mouse.wheel(0,1400)
    elif args.platform=='XHS':
     try:page.locator('.parent-comment,.comment-item').last.hover(timeout=3000)
     except Exception:pass
     page.mouse.wheel(0,1300)
    else:
     try:page.locator('.wbpro-scroller-item').last.hover(timeout=3000)
     except Exception:pass
     page.mouse.wheel(0,1000)
    page.wait_for_timeout(1500)
   state['streams'][stream]={'sort':sorts[stream],'history':history,'positions':len(pools[stream]),'stop': 'position_budget' if len(pools[stream])>=50 else stopped or 'loop_budget'}
   try:page.screenshot(path=str(out/(stream+'_排序与页面.png')),timeout=10000)
   except Exception as ex:state.setdefault('screenshot_errors',[]).append({'stream':stream,'error_type':type(ex).__name__,'time':now()})
  def action(page):
   global active,stopped
   page.wait_for_timeout(3500)
   stopped=block(page)
   if stopped:return
   if args.platform=='XHS':
    for _ in range(10):
     card=page.locator('section.note-item:has(a[href*="/explore/'+u['video_id']+'"])').first
     if card.count():card.click(timeout=5000);page.wait_for_timeout(3000);break
     stopped=block(page)
     if stopped:return
     page.mouse.wheel(0,650);page.wait_for_timeout(1000)
    else:stopped='known_card_not_in_bounded_search';return
    detail=page.evaluate('''id=>window.__INITIAL_STATE__?.note?.noteDetailMap?.[id]?.note?.noteId??null''',u['video_id'])
    if detail!=u['video_id']:stopped='target_detail_not_verified';return
   if args.platform=='BILI':
    try:page.locator('bili-comments').scroll_into_view_if_needed(timeout=10000)
    except Exception:pass
    page.wait_for_timeout(2000);sorts['H']='最热'
    page.evaluate('''() => {let h=document.querySelector('bili-comments')?.shadowRoot?.querySelector('bili-comments-header-renderer')?.shadowRoot;[...(h?.querySelectorAll('bili-text-button')??[])].find(n=>n.textContent.trim()==='最热')?.click()}''')
   elif args.platform=='WB':
    try:page.get_by_text('按热度',exact=True).click(timeout=3000);sorts['H']='按热度'
    except Exception:pass
   for r in pools['H'].values():r['sort_mode_observed']=sorts['H']
   scan(page,'H')
   if stopped in ['captcha','login_required','rate_limited']:return
   active='T';native=False
   if args.platform=='BILI':
    sorts['T']='最新'
    native=page.evaluate('''() => {let h=document.querySelector('bili-comments')?.shadowRoot?.querySelector('bili-comments-header-renderer')?.shadowRoot,n=[...(h?.querySelectorAll('bili-text-button')??[])].find(n=>n.textContent.trim()==='最新');if(n){n.click();return true}return false}''')
   elif args.platform=='WB':
    try:sorts['T']='按时间';page.get_by_text('按时间',exact=True).click(timeout=3000);native=True
    except Exception:pass
   if native:page.wait_for_timeout(2500)
   else:
    sorts['T']=sorts['H']+'延续第51至100位置（无原生时间序）'
    if len(pools['H'])<50:
     state['streams']['T']={'sort':'不可取得延续池：H不足50位置','positions':0,'history':[],'stop':'H_under_50_no_continuation'}
     return
    for x,source in overflow.values():add(x,source+'（正常批次溢出转入延续池）')
   scan(page,'T',not native)
   state['final_path']=page.url.split('?')[0];state['title']=page.title()
   page.remove_listener('response',response)
  original=next(v for v in seeds if v['event_id']==u['event_id'] and v['platform']==args.platform and v['video_id']==u['video_id'])
  query_number=args.query or (original.get('memberships')or[{'query':1}])[0]['query']
  state['normal_search_query_number']=query_number if args.platform=='XHS' else None
  search_term=cases[u['event_id']]['queries'][query_number-1]
  if args.platform=='XHS' and args.known_title:
   assert original.get('title'),'没有冻结标题，不能凭空补查询'
   search_term=original['title'].split('#')[0][:80];state['search_strategy']='known_title_same_video_ID_only'
  state['normal_search_term']=search_term if args.platform=='XHS' else None
  url='https://www.xiaohongshu.com/search_result?keyword='+quote(search_term) if args.platform=='XHS' else u['url']
  try:r=session.fetch(url,page_setup=setup,page_action=action);state['http_status']=r.status
  except Exception as ex:state['error']=str(ex)
  session.close_pages();state['blocked']=stopped if stopped in ['captcha','login_required','rate_limited'] else None
  state['stop_reason']=stopped;state['candidates']=[v for pool in pools.values() for v in pool.values()]
  # 同身份跨流统一为首次完整观察的正文和日期，保留每流位置与来源；原观察另存。
  state['raw_observations']=[dict(r) for r in state['candidates']]
  try:state['sample']=sample.sample_unit(state['candidates'],cfg,u['unit_id'])
  except Exception as ex:state['sample_error']=str(ex)
  state.update(ended_at=now(),elapsed_seconds=round(time.monotonic()-start,2),finished=False)
  state['status']=state['blocked'] or ('error' if state.get('error') or state.get('sample_error') else 'partial' if not state.get('sample',{}).get('baseline_unique_n') or any(g.get('gap',0) for g in state.get('sample',{}).get('quota_log',[])) else 'sampled')
  state['finished']=state['status']=='sampled'
  save(dest,state);print(json.dumps({'unit_id':u['unit_id'],'positions':[len(pools[k]) for k in ['H','T']],'baseline':state.get('sample',{}).get('baseline_unique_n'),'K':state.get('sample',{}).get('supplement_unique_n'),'blocked':state['blocked'],'stop':stopped,'error':state.get('error'),'sample_error':state.get('sample_error')},ensure_ascii=False),flush=True)
  if state['blocked']:break
  time.sleep(10)
