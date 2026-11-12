"""document access roles and two account roles

Revision ID: 0004_access_roles
Revises: 0003_conversation_mode
Create Date: 2026-11-11

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_access_roles"
down_revision: Union[str, Sequence[str], None] = "0003_conversation_mode"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("update users set role = 'user' where role = 'auditor'")
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.create_check_constraint("ck_users_role", "users", "role in ('admin', 'user')")
    op.add_column(
        "documents",
        sa.Column(
            "access_roles",
            postgresql.ARRAY(sa.String(length=32)),
            nullable=False,
            server_default="{}",
        ),
    )


def downgrade() -> None:
    op.drop_column("documents", "access_roles")
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.create_check_constraint("ck_users_role", "users", "role in ('admin', 'user', 'auditor')")
