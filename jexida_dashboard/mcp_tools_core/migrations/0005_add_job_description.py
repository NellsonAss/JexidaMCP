"""Migration to add description field to Job model.

This migration adds a description field to allow users to document
what each job does, making it easier to understand job history.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mcp_tools_core', '0004_seed_job_tools'),
    ]

    operations = [
        migrations.AddField(
            model_name='job',
            name='description',
            field=models.TextField(blank=True, help_text='Human-readable description of what this job does'),
        ),
    ]

