"""仅对未来已冻结的候选池抽样。不登录、不联网、不读取平台。"""
import json, hashlib, math, argparse
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]

def hash_order(seed, unit_id, layer, comment_key):
    value = '|'.join([seed, unit_id, layer, comment_key])
    return hashlib.sha256(value.encode('utf-8')).hexdigest(), comment_key

def draw(pool, target, seed, unit_id, layer):
    # 同一池内重复的评论ID只形成一个抽样单位，跨池成员资格保留。
    unique = {r['comment_key']: r for r in pool}
    return sorted(unique.values(), key=lambda r: hash_order(seed, unit_id, layer, r['comment_key']))[:target]

def sample_unit(records, config, unit_id):
    seed = config['seed']
    window_start, window_end = map(datetime.fromisoformat, config['comment_window'])
    h_quota = config['H_sample']
    t_quotas = config['T_sample_by_accessible_time_tercile']
    position_limit = config['positions_per_stream']
    positions = {'H': {}, 'T': {}}
    canonical = {}
    assert all(r['unit_id'] == unit_id for r in records)
    for r in records:
        assert r['stream'] in ['H', 'T']
        assert type(r['stream_position']) is int and 1 <= r['stream_position'] <= position_limit
        assert r.get('comment_key') and r.get('level') == 1
        previous = positions[r['stream']].setdefault(r['stream_position'], r['comment_key'])
        assert previous == r['comment_key'], '同一候选位置不能映射到不同评论身份'
        assert type(r.get('raw_text')) is str
        assert type(r.get('content_loaded')) is bool
        assert r.get('content_kind') in ['text', 'emoji', 'image', 'sticker', 'other_visible', 'technical_missing']
        assert r.get('sort_mode_observed'), '必须记录实际排序或降级'
        signature = tuple(r.get(k) for k in ['scope_status','time_lower','time_upper','raw_text','content_loaded','content_kind'])
        original = canonical.setdefault(r['comment_key'], signature)
        assert original == signature, '同身份内容或日期版本冲突；应保留观察版本并先核验统一，不能静默覆盖'
        if r['scope_status'] == 'in_window':
            assert r.get('time_lower') and r.get('time_upper'), '期内记录必须有日期上下界'
            lower, upper = map(datetime.fromisoformat, [r['time_lower'], r['time_upper']])
            assert lower.tzinfo and upper.tzinfo, '日期必须带时区'
            assert lower.utcoffset() == window_start.utcoffset() and upper.utcoffset() == window_start.utcoffset(), '日期必须统一为北京时间'
            assert window_start <= lower <= upper <= window_end, '期内标签与日期边界矛盾'
    for stream, pool in positions.items():
        assert len(set(pool.values())) <= position_limit, f'{stream}池超过候选身份预算'
    # 正文有关性、长度、表情、惩罚标签均不参与基线筛选。
    # 图片/贴纸等已加载的可见表达可没有文字，不能以strip()丢弃。
    eligible = [r for r in records if r['scope_status'] == 'in_window' and r['content_loaded']
                and r['content_kind'] != 'technical_missing']
    H = [r for r in eligible if r['stream'] == 'H']
    T = list({r['comment_key']: r for r in eligible if r['stream'] == 'T'}.values())
    T.sort(key=lambda r: (r['time_lower'], r['comment_key']))
    chunk = math.ceil(len(T) / 3)
    groups = [T[:chunk], T[chunk:2*chunk], T[2*chunk:]]
    targets = [('H', H, h_quota)] + [(f'T{i+1}', pool, q) for i, (pool, q) in enumerate(zip(groups, t_quotas))]
    members, gaps, roots = [], [], {}
    for layer, pool, quota in targets:
        selected = draw(pool, quota, seed, unit_id, layer)
        gaps.append({'unit_id': unit_id, 'layer': layer, 'eligible_pool_n': len({r['comment_key'] for r in pool}),
                     'target': quota, 'actual_members': len(selected), 'gap': quota-len(selected)})
        for r in selected:
            roots.setdefault(r['comment_key'], r)
            members.append({'unit_id': unit_id, 'comment_key': r['comment_key'], 'layer': layer,
                            'hash': hash_order(seed, unit_id, layer, r['comment_key'])[0]})
    baseline_keys = set(roots)
    union_pool = {r['comment_key']: r for r in eligible}
    keywords = config['supplement_keywords']
    kp = [r for key, r in union_pool.items() if key not in baseline_keys
          and any(term in r['raw_text'] for term in keywords)]
    k_limit = config['supplement_per_video_max']
    ks = draw(kp, k_limit, seed, unit_id, 'K')
    gaps.append({'unit_id': unit_id, 'layer': 'K', 'eligible_pool_n': len(kp),
                 'maximum': k_limit, 'actual_members': len(ks), 'unfilled_capacity': k_limit-len(ks)})
    for r in ks:
        roots[r['comment_key']] = r
        members.append({'unit_id': unit_id, 'comment_key': r['comment_key'], 'layer': 'K',
                        'matched_terms': [term for term in keywords if term in r['raw_text']],
                        'hash': hash_order(seed, unit_id, 'K', r['comment_key'])[0]})
    baseline = [roots[key] for key in sorted(baseline_keys)]
    context_roots = draw(baseline, config['reply_context']['roots_per_video'], seed, unit_id, 'CONTEXT')
    return {'unit_id': unit_id, 'baseline_unique_n': len(baseline),
            'baseline_members_n': sum(m['layer'] != 'K' for m in members),
            'supplement_unique_n': len(ks), 'root_records': list(roots.values()),
            'sample_memberships': members, 'quota_log': gaps,
            'context_root_keys': [r['comment_key'] for r in context_roots]}

