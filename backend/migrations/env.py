import os
from alembic import context
from sqlalchemy import create_engine, pool
from app.database import Base
from app import platform_models
configuration=context.config
url=os.getenv('DATABASE_URL','sqlite:///./finance-platform.db')
if context.is_offline_mode():
    raise RuntimeError('This baseline requires online migration execution')
else:
    engine=create_engine(url,poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection,target_metadata=Base.metadata)
        with context.begin_transaction(): context.run_migrations()
