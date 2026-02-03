from logging.config import fileConfig
import os
import sys
from dotenv import load_dotenv

# Добавляем путь к проекту в sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Загружаем переменные окружения
load_dotenv()

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context

# Импортируем Base из вашего приложения
from app.database import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Устанавливаем target_metadata для autogenerate
target_metadata = Base.metadata

# Получаем DATABASE_URL из .env или используем из alembic.ini
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    # Берем из alembic.ini
    DATABASE_URL = config.get_main_option("sqlalchemy.url")

# Переопределяем sqlalchemy.url в конфиге Alembic
if DATABASE_URL:
    config.set_main_option("sqlalchemy.url", DATABASE_URL)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
