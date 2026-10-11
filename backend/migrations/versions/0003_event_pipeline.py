"""Durable integration inbox and transactional projection outbox."""
from alembic import op
from app.platform_models import IntegrationMessage, IntegrationOutbox
revision='0003_event_pipeline'
down_revision='0002_source_dates'
branch_labels=None
depends_on=None
def upgrade():
    IntegrationMessage.__table__.create(op.get_bind(),checkfirst=True)
    IntegrationOutbox.__table__.create(op.get_bind(),checkfirst=True)
def downgrade():
    raise RuntimeError('Destructive downgrade disabled; restore a verified backup')
