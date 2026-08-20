FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt
COPY . /app
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
EXPOSE 8000
CMD ["python","-c","import live_enrichment; import uvicorn; uvicorn.run('backend.main:app', host='0.0.0.0', port=8000)"]
