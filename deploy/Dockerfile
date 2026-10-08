FROM python:3.12-slim
WORKDIR /app
COPY assistant/backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY assistant/backend/app ./app
COPY assistant/backend/alembic ./alembic
COPY assistant/backend/alembic.ini .
COPY index.html /course-docs/index.html
COPY assets /course-docs/assets
COPY courses /course-docs/courses
COPY docs-src /course-docs/docs-src
ENV ECE_DOCS_PATH=/course-docs PYTHONUNBUFFERED=1
RUN mkdir -p /app/data
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port \"${PORT:-8000}\""]
