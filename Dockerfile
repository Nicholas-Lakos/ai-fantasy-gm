FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt
COPY . /app

RUN python -m py_compile /app/backend/main.py /app/backend/show_server.py /app/backend/show_live.py

RUN python - <<'PY'
from pathlib import Path
p = Path('/app/frontend/index.html')
s = p.read_text(encoding='utf-8')
for tag in [
    '<script src="/fixes.js?v=20260824"></script>',
    '<script src="/fixes.js?v=20260827"></script>',
    '<script src="/fixes.js?v=20260828"></script>',
    '<script src="/fixes.js?v=20260829"></script>',
    '<script src="/fixes.js?v=20260830"></script>',
    '<script src="/fixes.js?v=20260831"></script>',
    '<script src="/live_ovr.js?v=20260826"></script>',
    '<script src="/live_ovr.js?v=20260827"></script>',
    '<script src="/live_ovr.js?v=20260828"></script>',
    '<script src="/live_ovr.js?v=20260829"></script>',
    '<script src="/live_ovr.js?v=20260830"></script>',
    '<script src="/live_ovr.js?v=20260831"></script>',
    '<script src="/live_ovr.js?v=20260901"></script>',
    '<script src="/fantasy_ovr.js?v=20260904"></script>',
]:
    s = s.replace(tag, '')
assets = '''<script>window.norm=window.norm||function(v){return String(v??'').toUpperCase()};</script><script src="/fixes.js?v=20260903"></script><script src="/fantasy_ovr.js?v=20260904"></script>'''
if assets not in s:
    s = s.replace('</body>', assets + '</body>') if '</body>' in s else s.replace('</html>', assets + '</html>')
p.write_text(s, encoding='utf-8')
PY

ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["python","-m","backend.show_server"]
