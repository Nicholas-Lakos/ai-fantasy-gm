FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt
COPY . /app

# Normalize the generated Live OVR block during the Docker build itself.
# This makes Render independent of GitHub Actions repair workflows.
RUN python /app/backend/normalize_live_ovr.py
RUN python -m py_compile /app/backend/main.py /app/backend/show_server.py /app/backend/show_live.py

# Force the current frontend assets into the page and prevent stale cached scripts.
RUN python - <<'PY'
from pathlib import Path
p = Path('/app/frontend/index.html')
s = p.read_text(encoding='utf-8')
for tag in [
    '<script src="/fixes.js?v=20260824"></script>',
    '<script src="/fixes.js?v=20260827"></script>',
    '<script src="/live_ovr.js?v=20260826"></script>',
    '<script src="/live_ovr.js?v=20260827"></script>',
]:
    s = s.replace(tag, '')
assets = '<script src="/fixes.js?v=20260828"></script><script src="/live_ovr.js?v=20260828"></script><script>window.norm=window.norm||function(v){return String(v||\'\').toUpperCase()};</script>'
if assets not in s:
    s = s.replace('</body>', assets + '</body>') if '</body>' in s else s.replace('</html>', assets + '</html>')
p.write_text(s, encoding='utf-8')
PY

ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["python","-m","backend.show_server"]
