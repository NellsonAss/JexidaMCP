"""Create AI logic flow versioning and logging tables.

Revision ID: 004_create_ai_logic_flow_tables
Revises: 003_create_reference_tables
Create Date: 2024-12-05

Creates tables for:
- ai_logic_versions: Track versions of AI logic/strategy
- ai_logic_flow_logs: Capture step-by-step flow details for analysis
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '004_create_ai_logic_flow_tables'
down_revision = '003_create_reference_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create AI logic flow versioning and logging tables."""
    
    # Create logic step type enum
    logic_step_type_enum = sa.Enum(
        'flow_start', 'conversation_load', 'context_build', 'reference_fetch',
        'history_load', 'context_truncate', 'llm_call', 'llm_response',
        'tool_decision', 'tool_execute', 'tool_result', 'iteration_start',
        'iteration_end', 'message_save', 'flow_end', 'flow_error',
        name='logicsteptype'
    )
    
    # Create ai_logic_versions table
    op.create_table(
        'ai_logic_versions',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('version_id', sa.String(50), nullable=False, unique=True, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('configuration', sa.JSON(), nullable=False),
        sa.Column('system_prompt_hash', sa.String(64), nullable=True),
        sa.Column('max_iterations', sa.Integer(), nullable=False, server_default='10'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='0', index=True),
        sa.Column('is_baseline', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('deprecated_at', sa.DateTime(), nullable=True),
    )
    
    # Create ai_logic_flow_logs table
    op.create_table(
        'ai_logic_flow_logs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('logic_version_id', sa.Integer(), 
                  sa.ForeignKey('ai_logic_versions.id', ondelete='SET NULL'), 
                  nullable=True, index=True),
        sa.Column('conversation_id', sa.Integer(), nullable=True, index=True),
        sa.Column('message_id', sa.Integer(), nullable=True, index=True),
        sa.Column('turn_index', sa.Integer(), nullable=True),
        sa.Column('step_type', logic_step_type_enum, nullable=False, index=True),
        sa.Column('step_name', sa.String(255), nullable=False),
        sa.Column('step_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('input_data', sa.JSON(), nullable=True),
        sa.Column('output_data', sa.JSON(), nullable=True),
        sa.Column('duration_ms', sa.Float(), nullable=True),
        sa.Column('tokens_used', sa.Integer(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, 
                  server_default=sa.text('CURRENT_TIMESTAMP'), index=True),
    )
    
    # Create index for common query patterns
    op.create_index(
        'ix_ai_logic_flow_logs_version_conversation',
        'ai_logic_flow_logs',
        ['logic_version_id', 'conversation_id']
    )
    
    op.create_index(
        'ix_ai_logic_flow_logs_step_type_created',
        'ai_logic_flow_logs',
        ['step_type', 'created_at']
    )


def downgrade() -> None:
    """Drop AI logic flow tables."""
    # Drop indexes first
    op.drop_index('ix_ai_logic_flow_logs_step_type_created', table_name='ai_logic_flow_logs')
    op.drop_index('ix_ai_logic_flow_logs_version_conversation', table_name='ai_logic_flow_logs')
    
    # Drop tables
    op.drop_table('ai_logic_flow_logs')
    op.drop_table('ai_logic_versions')
    
    # Drop enum
    sa.Enum(name='logicsteptype').drop(op.get_bind(), checkfirst=True)

