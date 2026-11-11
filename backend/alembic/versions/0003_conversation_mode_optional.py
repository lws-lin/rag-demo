"""conversation mode is decided during the chat

Revision ID: 0003_conversation_mode
Revises: 0002_chunks
Create Date: 2026-11-11

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_conversation_mode"
down_revision: Union[str, Sequence[str], None] = "0002_chunks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_conversations_mode", "conversations", type_="check")
    op.alter_column("conversations", "mode", existing_type=sa.String(length=32), nullable=True)
    op.create_check_constraint(
        "ck_conversations_mode",
        "conversations",
        "mode is null or mode in ('qa', 'proposal')",
    )


def downgrade() -> None:
    op.execute("update conversations set mode = 'qa' where mode is null")
    op.drop_constraint("ck_conversations_mode", "conversations", type_="check")
    op.alter_column("conversations", "mode", existing_type=sa.String(length=32), nullable=False)
    op.create_check_constraint(
        "ck_conversations_mode",
        "conversations",
        "mode in ('qa', 'proposal')",
    )
