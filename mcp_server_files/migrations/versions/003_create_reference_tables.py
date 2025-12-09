"""Create reference context management tables.

Revision ID: 003_create_reference_tables
Revises: 002_create_assistant_tables
Create Date: 2024-12-04

Creates tables for:
- reference_snippets: Reusable prompt fragments with targeting
- reference_profiles: Named collections of snippets
- reference_profile_snippets: Join table for profile-snippet relationships
- reference_logs: Audit log of references used per response
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '003_create_reference_tables'
down_revision = '002_create_assistant_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create reference context management tables."""
    
    # Create reference category enum
    reference_category_enum = sa.Enum(
        'system_behavior', 'tool_usage', 'domain_knowledge', 
        'style_guide', 'page_context', 'role_context', 'other',
        name='referencecategory'
    )
    
    # Create reference_snippets table
    op.create_table(
        'reference_snippets',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('key', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('category', reference_category_enum, nullable=False, server_default='other'),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('applicable_tools', sa.JSON(), nullable=True),
        sa.Column('applicable_roles', sa.JSON(), nullable=True),
        sa.Column('applicable_modes', sa.JSON(), nullable=True),
        sa.Column('applicable_pages', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    
    # Create reference_profiles table
    op.create_table(
        'reference_profiles',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('key', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    
    # Create reference_profile_snippets join table
    op.create_table(
        'reference_profile_snippets',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('profile_id', sa.Integer(), sa.ForeignKey('reference_profiles.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('snippet_id', sa.Integer(), sa.ForeignKey('reference_snippets.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('order_index', sa.Integer(), nullable=False, server_default='0'),
        sa.UniqueConstraint('profile_id', 'snippet_id', name='uq_profile_snippet'),
    )
    
    # Create reference_logs table
    op.create_table(
        'reference_logs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('conversation_id', sa.Integer(), nullable=True, index=True),
        sa.Column('message_id', sa.Integer(), nullable=True, index=True),
        sa.Column('turn_index', sa.Integer(), nullable=True),
        sa.Column('assembled_system_prompt', sa.Text(), nullable=False),
        sa.Column('referenced_snippets', sa.JSON(), nullable=False),
        sa.Column('model_id', sa.String(255), nullable=True),
        sa.Column('strategy_id', sa.String(255), nullable=True),
        sa.Column('profile_key', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )


def downgrade() -> None:
    """Drop reference context management tables."""
    op.drop_table('reference_logs')
    op.drop_table('reference_profile_snippets')
    op.drop_table('reference_profiles')
    op.drop_table('reference_snippets')
    
    # Drop enum
    sa.Enum(name='referencecategory').drop(op.get_bind(), checkfirst=True)


