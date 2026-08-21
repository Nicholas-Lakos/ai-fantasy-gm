FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt
COPY . /app
RUN sed -i 's#</body>#<script src="/fixes.js"></script></body>#' /app/frontend/index.html
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["python","-m","backend.run"]
