"""Organization reconciliation cadence and observable staleness thresholds."""
from alembic import op
from app.platform_models import ReconciliationPolicy
revision='0004_reconciliation_policy'
down_revision='0003_event_pipeline'
branch_labels=None
depends_on=None
def upgrade():
    ReconciliationPolicy.__table__.create(op.get_bind(),checkfirst=True)
def downgrade():
    raise RuntimeError('Destructive downgrade disabled; restore a verified backup')
