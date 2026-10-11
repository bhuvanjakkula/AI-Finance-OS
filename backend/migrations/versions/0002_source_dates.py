"""Separate transaction date and reporting period from posting date."""
from alembic import op
import sqlalchemy as sa
revision='0002_source_dates'
down_revision='0001_platform'
branch_labels=None
depends_on=None

def upgrade():
    columns={c['name'] for c in sa.inspect(op.get_bind()).get_columns('journal_entries')}
    if 'transaction_date' not in columns: op.add_column('journal_entries',sa.Column('transaction_date',sa.String(10),nullable=True))
    if 'period' not in columns: op.add_column('journal_entries',sa.Column('period',sa.String(7),nullable=True))
    op.execute(sa.text('UPDATE journal_entries SET transaction_date=posting_date WHERE transaction_date IS NULL'))
    op.execute(sa.text('UPDATE journal_entries SET period=substr(posting_date,1,7) WHERE period IS NULL'))

def downgrade():
    raise RuntimeError('Destructive downgrade disabled; restore a verified backup')
