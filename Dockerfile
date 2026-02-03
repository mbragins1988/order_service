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

# Копируем код приложения
COPY app/ ./app/

# Запускаем приложение
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
