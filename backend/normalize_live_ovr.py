from pathlib import Path
import re

p = Path('backend/main.py')
s = p.read_text(encoding='utf-8')
marker = '# LIVE_SHOW_OVR_SYSTEM_V1'
app_marker = 'app=FastAPI('
start = s.find(marker)
if start < 0:
    raise SystemExit('Live OVR marker not found')
app_pos = s.find(app_marker)
if app_pos < 0:
    raise SystemExit('FastAPI app initialization not found')
end = s.find(app_marker, start)
if end < 0:
    raise SystemExit('FastAPI app initialization after Live OVR block not found')

block = s[start:end]
# Previous patches have existed with either one or two literal backslashes before n.
block = block.replace('\\\\n', '\n').replace('\\n', '\n')

prefix = s[:start]
suffix = s[app_pos:]
line_end = suffix.find('\n')
if line_end < 0:
    line_end = len(suffix)
app_line = suffix[:line_end]
rest = suffix[line_end:]
if rest.startswith('\\n'):
    rest = rest[2:]
elif rest.startswith('\n'):
    rest = rest[1:]

new = prefix + app_line + '\n' + block.rstrip('\n') + '\n' + rest.lstrip('\n')
# The damaged prefix can contain one or more literal backslash-n pairs immediately before app.
new = re.sub(r'(?:\\+n)+app=FastAPI', '\napp=FastAPI', new, count=1)

if new == s:
    print('main.py already normalized')
else:
    p.write_text(new, encoding='utf-8')
    print('Repaired backend/main.py')
