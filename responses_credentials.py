"""Explicit future .env access only. No environment fallback, expansion or file writes."""
import os,re,stat
from pathlib import Path

def load_key_file(path):
 # Call only after action-time credential-use approval and deliberate live opt-in.
 descriptor=os.open(Path(path),os.O_RDONLY|os.O_NOFOLLOW)
 with os.fdopen(descriptor,'rb') as stream:
  info=os.fstat(stream.fileno())
  if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&0o077 or info.st_size>8192:raise ValueError('owner-only bounded regular key file required')
  raw=stream.read(8193)
 if len(raw)>8192:raise ValueError('key file bound')
 try:
  lines=[line.strip() for line in raw.decode('utf-8').splitlines() if line.strip() and not line.lstrip().startswith('#')]
  if len(lines)!=1 or not lines[0].startswith('OPENAI_API_KEY='):raise ValueError()
  key=lines[0].split('=',1)[1]
  if not re.fullmatch(r'[A-Za-z0-9_-]{16,512}',key):raise ValueError()
 except (UnicodeError,ValueError):raise ValueError('one nonempty OPENAI_API_KEY assignment required; no interpolation or extra keys') from None
 return key
