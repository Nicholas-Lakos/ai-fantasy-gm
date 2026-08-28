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
    '<script src="/live_ovr.js?v=20260826"></script>',
    '<script src="/live_ovr.js?v=20260827"></script>',
    '<script src="/fixes.js?v=20260828"></script>',
    '<script src="/live_ovr.js?v=20260828"></script>',
    '<script src="/fixes.js?v=20260829"></script>',
    '<script src="/live_ovr.js?v=20260829"></script>',
    '<script src="/fixes.js?v=20260830"></script>',
    '<script src="/live_ovr.js?v=20260830"></script>',
]:
    s = s.replace(tag, '')
assets = '''<script src="/fixes.js?v=20260831"></script><script src="/live_ovr.js?v=20260831"></script><script>
(function(){
  const fallback={"yoshinobu yamamoto":87,"hunter brown":82,"geraldo perdomo":77,"nico hoerner":80,"josh naylor":76,"shota imanaga":81,"luis arraez":81,"jac caglianone":78,"trevor megill":83};
  const key=s=>String(s||'').normalize('NFD').replace(/[\\u0300-\\u036f]/g,'').toLowerCase().replace(/[^a-z0-9 ]/g,'').replace(/\\s+/g,' ').trim();
  const paint=()=>document.querySelectorAll('#roster tr,#opRoster tr,#waiverRows tr').forEach(row=>{const n=row.querySelector('.pn');const a=row.querySelector('.avatar');if(!n||!a)return;const k=key(n.textContent);let o=window.SHOW_LIVE_RATINGS?.[k];if(!Number.isFinite(o))o=fallback[k];if(!Number.isFinite(o))return;a.textContent=String(o);a.dataset.showOvr=String(o);a.title='MLB The Show 26 Live Series Overall';a.classList.add(o>=90?'show-elite':o>=80?'show-great':o>=70?'show-good':o>=60?'show-average':o>=50?'show-below':'show-poor')});
  const load=async()=>{const names=[...document.querySelectorAll('#roster .pn,#opRoster .pn,#waiverRows .pn')].map(x=>x.textContent.trim()).filter(Boolean);if(!names.length){paint();return}try{const q=names.map(n=>'names='+encodeURIComponent(n)).join('&');const r=await fetch('/api/show/live-ratings?'+q+'&_='+Date.now(),{cache:'no-store',credentials:'include'});if(r.ok){const d=await r.json();window.SHOW_LIVE_RATINGS=window.SHOW_LIVE_RATINGS||{};(d.players||[]).forEach(p=>{const o=Number(p.overall);if(p.name&&Number.isFinite(o))window.SHOW_LIVE_RATINGS[key(p.name)]=o})}}catch(e){}paint()};
  const obs=new MutationObserver(()=>{paint();clearTimeout(window.__ovrt);window.__ovrt=setTimeout(load,250)});['roster','opRoster','waiverRows'].forEach(id=>{const e=document.getElementById(id);if(e)obs.observe(e,{childList:true,subtree:true})});window.addEventListener('load',load);setTimeout(load,500);setTimeout(load,2000);setTimeout(load,5000);paint();
})();
</script>'''
if assets not in s:
    s = s.replace('</body>', assets + '</body>') if '</body>' in s else s.replace('</html>', assets + '</html>')
p.write_text(s, encoding='utf-8')
PY

ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["python","-m","backend.show_server"]
