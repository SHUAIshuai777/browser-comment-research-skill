import json
from datetime import datetime, timezone

def ensure_allowed(project, platform):
    record=json.loads((project/'inputs'/'access.json').read_text())[platform]
    if record.get('approved') is not True or not record.get('basis') or not record.get('robots_review'):
        raise SystemExit('尚未登记该平台已核实的访问依据与规则；不能仅因账号可登录就视为许可')
    stamp=datetime.fromisoformat(record['reviewed_at'])
    if stamp.tzinfo is None or not 0 <= (datetime.now(timezone.utc)-stamp).total_seconds() <= 86400:
        raise SystemExit('访问规则记录须在24小时内核实，并带时区')
