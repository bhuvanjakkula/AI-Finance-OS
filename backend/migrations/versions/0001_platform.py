"""Add canonical platform tables while retaining original demo tables."""
from alembic import op
from app.database import Base
from app import platform_models
revision='0001_platform'
down_revision=None
branch_labels=None
depends_on=None

def upgrade():
    Base.metadata.create_all(bind=op.get_bind(),checkfirst=True)

def downgrade():
    raise RuntimeError('Destructive downgrade disabled. Restore a verified backup to revert this baseline.')
