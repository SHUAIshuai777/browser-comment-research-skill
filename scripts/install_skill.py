import argparse,shutil
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('--destination',type=Path,default=Path.home()/'.codex/skills');a=ap.parse_args()
src=Path(__file__).resolve().parents[1];dest=a.destination/'browser-comment-research'
if dest.exists():raise SystemExit('已存在同名 Skill，拒绝覆盖；请自行备份旧版后重试')
shutil.copytree(src,dest,ignore=shutil.ignore_patterns('.git','.venv','__pycache__','*.pyc','.private','data','outputs'))
print(dest)
