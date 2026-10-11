"""Initial schema

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enums
    op.execute("CREATE TYPE videostatus AS ENUM ('pending', 'downloading', 'downloaded', 'failed')")
    op.execute("CREATE TYPE clipstatus AS ENUM ('pending', 'processing', 'ready', 'failed')")
    op.execute("CREATE TYPE poststatus AS ENUM ('draft', 'scheduled', 'publishing', 'published', 'failed')")

    # source_videos table
    op.create_table(
        'source_videos',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('youtube_id', sa.String(20), nullable=False),
        sa.Column('channel_id', sa.String(50), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('thumbnail_url', sa.String(500), nullable=True),
        sa.Column('status', postgresql.ENUM('pending', 'downloading', 'downloaded', 'failed', name='videostatus', create_type=False), nullable=False, server_default='pending'),
        sa.Column('local_path', sa.String(500), nullable=True),
        sa.Column('file_size_bytes', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('discovered_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('downloaded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('youtube_id', name='uq_source_videos_youtube_id'),
    )
    op.create_index('ix_source_videos_channel_discovered', 'source_videos', ['channel_id', 'discovered_at'])
    op.create_index('ix_source_videos_youtube_id', 'source_videos', ['youtube_id'], unique=True)

    # clips table
    op.create_table(
        'clips',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source_video_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('clip_index', sa.Integer(), nullable=False),
        sa.Column('start_seconds', sa.Float(), nullable=False),
        sa.Column('end_seconds', sa.Float(), nullable=False),
        sa.Column('duration_seconds', sa.Float(), nullable=False),
        sa.Column('status', postgresql.ENUM('pending', 'processing', 'ready', 'failed', name='clipstatus', create_type=False), nullable=False, server_default='pending'),
        sa.Column('local_path', sa.String(500), nullable=True),
        sa.Column('storage_url', sa.String(500), nullable=True),
        sa.Column('file_size_bytes', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('caption', sa.Text(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('hashtags', sa.Text(), nullable=True),
        sa.Column('alt_text', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['source_video_id'], ['source_videos.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source_video_id', 'clip_index', name='uq_clip_source_index'),
    )
    op.create_index('ix_clips_status_created', 'clips', ['status', 'created_at'])
    op.create_index('ix_clips_source_video_id', 'clips', ['source_video_id'])

    # posts table
    op.create_table(
        'posts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('clip_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', postgresql.ENUM('draft', 'scheduled', 'publishing', 'published', 'failed', name='poststatus', create_type=False), nullable=False, server_default='draft'),
        sa.Column('ig_media_id', sa.String(50), nullable=True),
        sa.Column('ig_permalink', sa.String(500), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['clip_id'], ['clips.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_posts_clip_id', 'posts', ['clip_id'])
    op.create_index('ix_posts_scheduled_at', 'posts', ['scheduled_at'])
    op.create_index('ix_posts_status', 'posts', ['status'])


def downgrade() -> None:
    op.drop_table('posts')
    op.drop_table('clips')
    op.drop_table('source_videos')
    op.execute("DROP TYPE poststatus")
    op.execute("DROP TYPE clipstatus")
    op.execute("DROP TYPE videostatus")