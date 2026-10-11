"""Independent close approval and period controls."""
from alembic import op
from app.platform_models import PeriodControl
revision='0005_period_controls'
down_revision='0004_reconciliation_policy'
branch_labels=None
depends_on=None
def upgrade():
    PeriodControl.__table__.create(op.get_bind(),checkfirst=True)
def downgrade():
    raise RuntimeError('Destructive downgrade disabled; restore a verified backup')
