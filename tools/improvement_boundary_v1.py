"""Reject actor-controlled links/special files before host content reads."""
import os,pathlib,stat
IGNORED={'.git','.dart_tool','build','__pycache__'}
def inspect_repo(repo):
 repo=pathlib.Path(repo)
 if repo.is_symlink() or not repo.is_dir():raise ValueError('Invalid repository root')
 violations=[]
 for parent,dirs,files in os.walk(repo,followlinks=False):
  dirs[:]=[d for d in dirs if d not in IGNORED]
  for name in dirs+files:
   path=pathlib.Path(parent)/name;mode=path.lstat().st_mode
   if stat.S_ISLNK(mode) or not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
    violations.append(str(path.relative_to(repo)))
 if violations:raise ValueError('Unsafe actor artifact paths (targets not read): '+repr(sorted(violations)))
 return True
