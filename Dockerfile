# Dockerfile
FROM python:3.10-slim

# Устанавливаем uv и системные зависимости для PostgreSQL
RUN pip install uv && \
    apt-get update && \
    apt-get install -y gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копируем файлы зависимостей
COPY pyproject.toml uv.lock ./

# Устанавливаем зависимости в систему
RUN uv pip install --system --no-cache -r pyproject.toml
USER appuser
# Копируем Alembic миграции
COPY alembic.ini .
COPY alembic/ ./alembic/

# Копируем entrypoint
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# Копируем код приложения
COPY app/ ./app/

# Запускаем через entrypoint
ENTRYPOINT ["./entrypoint.sh"]
