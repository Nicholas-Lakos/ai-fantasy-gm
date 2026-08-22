FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt
COPY . /app
RUN python -c "p='/app/frontend/index.html'; s=open(p,encoding='utf-8').read(); import re; s=re.sub(r'<script src=\"/fixes\\.js\\?v=[^\"]+\"></script>','',s); tag='<script src=\"/fixes.js?v=20260822-clean1\"></script>'; s=(s.replace('</body>',tag+'</body>') if '</body>' in s else s.replace('</html>',tag+'</html>') if '</html>' in s else s+'\\n'+tag+'\\n'); open(p,'w',encoding='utf-8').write(s)"
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["python","-m","backend.run"]
