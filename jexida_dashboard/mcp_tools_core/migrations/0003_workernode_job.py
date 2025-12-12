"""Migration to add WorkerNode and Job models for the job system.

This migration creates the database tables for:
- mcp_worker_nodes: Remote worker nodes that can execute jobs
- mcp_jobs: Jobs dispatched to worker nodes
"""

import uuid
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('mcp_tools_core', '0002_seed_tools'),
    ]

    operations = [
        migrations.CreateModel(
            name='WorkerNode',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text="Unique node identifier (e.g., 'node-ubuntu-0')", max_length=100, unique=True)),
                ('host', models.CharField(help_text='Hostname or IP address of the worker node', max_length=255)),
                ('user', models.CharField(help_text='SSH username for connecting to the node', max_length=100)),
                ('ssh_port', models.IntegerField(default=22, help_text='SSH port number')),
                ('tags', models.CharField(blank=True, help_text="Comma-separated tags for categorization (e.g., 'ubuntu,gpu,worker')", max_length=255)),
                ('is_active', models.BooleanField(default=True, help_text='Whether this node is available for jobs')),
                ('last_seen', models.DateTimeField(blank=True, help_text='When this node was last successfully contacted', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Worker Node',
                'verbose_name_plural': 'Worker Nodes',
                'db_table': 'mcp_worker_nodes',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='Job',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, help_text='Unique job identifier', primary_key=True, serialize=False)),
                ('command', models.TextField(help_text='Shell command to execute on the worker node')),
                ('status', models.CharField(choices=[('queued', 'Queued'), ('running', 'Running'), ('succeeded', 'Succeeded'), ('failed', 'Failed')], default='queued', help_text='Current job status', max_length=20)),
                ('stdout', models.TextField(blank=True, help_text='Standard output from the command')),
                ('stderr', models.TextField(blank=True, help_text='Standard error from the command')),
                ('exit_code', models.IntegerField(blank=True, help_text='Exit code from the command (0 = success)', null=True)),
                ('duration_ms', models.IntegerField(blank=True, help_text='Execution duration in milliseconds', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('target_node', models.ForeignKey(help_text='The worker node this job runs on', on_delete=django.db.models.deletion.CASCADE, related_name='jobs', to='mcp_tools_core.workernode')),
            ],
            options={
                'verbose_name': 'Job',
                'verbose_name_plural': 'Jobs',
                'db_table': 'mcp_jobs',
                'ordering': ['-created_at'],
            },
        ),
    ]

