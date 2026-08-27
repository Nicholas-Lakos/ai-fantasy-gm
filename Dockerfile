FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt
COPY . /app
RUN python -c "p='/app/frontend/index.html'; s=open(p,encoding='utf-8').read(); tag='<script src=\"/fixes.js?v=20260827\"></script>'; live='<script src=\"/live_ovr.js?v=20260827\"></script>'; s=s.replace('<script src=\"/fixes.js?v=20260824\"></script>',''); s=s.replace('<script src=\"/fixes.js?v=20260827\"></script>',''); s=s.replace('<script src=\"/live_ovr.js?v=20260826\"></script>',''); s=s.replace('<script src=\"/live_ovr.js?v=20260827\"></script>',''); s=s.replace('</body>',tag+live+'</body>') if '</body>' in s else s.replace('</html>',tag+live+'</html>') if '</html>' in s else s+'\\n'+tag+live+'\\n'; open(p,'w',encoding='utf-8').write(s)"
# The Live OVR routes were added before FastAPI app initialization. Normalize that ordering during the image build.
RUN python -c "p='/app/backend/main.py'; s=open(p,encoding='utf-8').read(); marker='\\n# LIVE_SHOW_OVR_SYSTEM_V1'; mi=s.index(marker); ai=s.index('app=FastAPI',mi); end=s.index('\\n',ai); init=s[ai:end]; s=s[:ai]+s[end:]; mi=s.index(marker); s=s[:mi]+init+'\\n'+s[mi:]; open(p,'w',encoding='utf-8').write(s); compile(s,'/app/backend/main.py','exec')"
RUN python -m py_compile /app/backend/main.py /app/backend/show_server.py /app/backend/show_live.py
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["python","-m","backend.show_server"]
