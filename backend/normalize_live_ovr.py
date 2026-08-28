from pathlib import Path

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
# The previous generator wrote literal backslash-n sequences into this generated block.
block = block.replace('\\n', '\n')

# Remove the generated block from its old position and put it immediately after app initialization.
prefix = s[:start]
suffix = s[app_pos:]
line_end = suffix.find('\n')
if line_end < 0:
    line_end = len(suffix)
app_line = suffix[:line_end]
rest = suffix[line_end:]
if rest.startswith('\n'):
    rest = rest[1:]

new = prefix + app_line + '\n' + block.rstrip('\n') + '\n' + rest.lstrip('\n')

if new == s:
    print('main.py already normalized')
else:
    p.write_text(new, encoding='utf-8')
    print('Repaired backend/main.py')
