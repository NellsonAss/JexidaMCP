"""Create assistant tables for AI chatbot.

Revision ID: 002_create_assistant_tables
Revises: 001_create_secrets_table
Create Date: 2024-12-03

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002_create_assistant_tables'
down_revision = '001_create_secrets_table'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create assistant_conversations, assistant_messages, and assistant_action_logs tables."""
    
    # Create conversation mode enum
    conversation_mode_enum = sa.Enum(
        'default', 'technical', 'casual', 'brief', 'verbose',
        name='conversationmode'
    )
    
    # Create message role enum
    message_role_enum = sa.Enum(
        'system', 'user', 'assistant', 'tool',
        name='messagerole'
    )
    
    # Create action status enum
    action_status_enum = sa.Enum(
        'pending', 'confirmed', 'executed', 'failed', 'cancelled',
        name='actionstatus'
    )
    
    # Create assistant_conversations table
    op.create_table(
        'assistant_conversations',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.String(255), nullable=True, index=True),
        sa.Column('title', sa.String(500), nullable=True),
        sa.Column('mode', conversation_mode_enum, nullable=False, server_default='default'),
        sa.Column('context', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    
    # Create assistant_messages table
    op.create_table(
        'assistant_messages',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('conversation_id', sa.Integer(), sa.ForeignKey('assistant_conversations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('role', message_role_enum, nullable=False),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('tool_calls', sa.JSON(), nullable=True),
        sa.Column('tool_call_id', sa.String(255), nullable=True),
        sa.Column('name', sa.String(255), nullable=True),
        sa.Column('tokens_used', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    
    # Create assistant_action_logs table
    op.create_table(
        'assistant_action_logs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('conversation_id', sa.Integer(), sa.ForeignKey('assistant_conversations.id', ondelete='CASCADE'), nullable=True, index=True),
        sa.Column('action_name', sa.String(255), nullable=False, index=True),
        sa.Column('action_type', sa.String(50), nullable=False),
        sa.Column('parameters', sa.JSON(), nullable=True),
        sa.Column('result', sa.JSON(), nullable=True),
        sa.Column('status', action_status_enum, nullable=False, server_default='pending'),
        sa.Column('confirmation_id', sa.String(255), nullable=True, index=True),
        sa.Column('user_id', sa.String(255), nullable=True, index=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('executed_at', sa.DateTime(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """Drop assistant tables."""
    op.drop_table('assistant_action_logs')
    op.drop_table('assistant_messages')
    op.drop_table('assistant_conversations')
    
    # Drop enums
    sa.Enum(name='actionstatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='messagerole').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='conversationmode').drop(op.get_bind(), checkfirst=True)

