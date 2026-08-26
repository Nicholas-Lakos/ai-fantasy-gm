FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt
COPY . /app
RUN python -c "p='/app/frontend/index.html'; s=open(p,encoding='utf-8').read(); tag='<script src=\"/fixes.js?v=20260824\"></script>'; live='<script src=\"/live_ovr.js?v=20260826\"></script>'; s=s.replace(tag,''); s=s.replace(live,''); s=s.replace('</body>',tag+live+'</body>') if '</body>' in s else s.replace('</html>',tag+live+'</html>') if '</html>' in s else s+'\n'+tag+live+'\n'; open(p,'w',encoding='utf-8').write(s)"
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["python","-m","backend.show_server"]
