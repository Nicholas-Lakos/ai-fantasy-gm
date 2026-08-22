FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt
COPY . /app
RUN python -c "p='/app/frontend/index.html'; s=open(p,encoding='utf-8').read(); import re; s=re.sub(r'<script src=\"/fixes\\.js\\?v=[^\"]+\"></script>','',s); s=re.sub(r'<script src=\"/league-fix\\.js\\?v=[^\"]+\"></script>','',s); tag1='<script src=\"/fixes.js?v=20260822-clean3\"></script>'; tag2='<script src=\"/league-fix.js?v=20260822-league1\"></script>'; insert=tag1+tag2; s=(s.replace('</body>',insert+'</body>') if '</body>' in s else s.replace('</html>',insert+'</html>') if '</html>' in s else s+'\\n'+insert+'\\n'); open(p,'w',encoding='utf-8').write(s)"
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["python","-m","backend.run"]
