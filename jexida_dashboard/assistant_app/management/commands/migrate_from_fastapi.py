"""Management command to migrate data from FastAPI SQLite database.

This is a one-time migration script that:
1. Connects to the existing FastAPI SQLite database
2. Reads secrets, conversations, messages, and action logs
3. Creates corresponding Django model instances
4. Preserves encrypted values (same encryption key used)

Usage:
    python manage.py migrate_from_fastapi --source /path/to/secrets.db
"""

import sqlite3
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from secrets_app.models import Secret
from assistant_app.models import Conversation, Message, ActionLog


class Command(BaseCommand):
    help = "Migrate data from FastAPI SQLite database to Django"
    
    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            type=str,
            required=True,
            help="Path to the source SQLite database (e.g., /path/to/secrets.db)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be migrated without making changes",
        )
    
    def handle(self, *args, **options):
        source_db = Path(options["source"])
        dry_run = options["dry_run"]
        
        if not source_db.exists():
            raise CommandError(f"Source database not found: {source_db}")
        
        self.stdout.write(f"Migrating from: {source_db}")
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - No changes will be made"))
        
        # Connect to source database
        conn = sqlite3.connect(str(source_db))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            # Migrate secrets
            self._migrate_secrets(cursor, dry_run)
            
            # Migrate conversations
            self._migrate_conversations(cursor, dry_run)
            
            # Migrate messages
            self._migrate_messages(cursor, dry_run)
            
            # Migrate action logs
            self._migrate_action_logs(cursor, dry_run)
            
            self.stdout.write(self.style.SUCCESS("Migration completed!"))
            
        finally:
            conn.close()
    
    def _migrate_secrets(self, cursor, dry_run):
        """Migrate secrets table."""
        self.stdout.write("Migrating secrets...")
        
        try:
            cursor.execute("SELECT * FROM secrets")
            rows = cursor.fetchall()
        except sqlite3.OperationalError:
            self.stdout.write(self.style.WARNING("No secrets table found"))
            return
        
        count = 0
        for row in rows:
            if dry_run:
                self.stdout.write(f"  Would migrate secret: {row['name']} ({row['service_type']}/{row['key']})")
            else:
                # Check if already exists
                if not Secret.objects.filter(service_type=row["service_type"], key=row["key"]).exists():
                    Secret.objects.create(
                        name=row["name"],
                        service_type=row["service_type"],
                        key=row["key"],
                        encrypted_value=row["encrypted_value"],
                    )
                    count += 1
        
        self.stdout.write(f"  Migrated {count} secrets")
    
    def _migrate_conversations(self, cursor, dry_run):
        """Migrate assistant_conversations table."""
        self.stdout.write("Migrating conversations...")
        
        try:
            cursor.execute("SELECT * FROM assistant_conversations")
            rows = cursor.fetchall()
        except sqlite3.OperationalError:
            self.stdout.write(self.style.WARNING("No assistant_conversations table found"))
            return
        
        count = 0
        for row in rows:
            if dry_run:
                self.stdout.write(f"  Would migrate conversation: {row['id']}")
            else:
                if not Conversation.objects.filter(id=row["id"]).exists():
                    Conversation.objects.create(
                        id=row["id"],
                        title=row.get("title", ""),
                        mode=row.get("mode", "default"),
                        context=row.get("context", {}),
                        is_active=row.get("is_active", True),
                    )
                    count += 1
        
        self.stdout.write(f"  Migrated {count} conversations")
    
    def _migrate_messages(self, cursor, dry_run):
        """Migrate assistant_messages table."""
        self.stdout.write("Migrating messages...")
        
        try:
            cursor.execute("SELECT * FROM assistant_messages")
            rows = cursor.fetchall()
        except sqlite3.OperationalError:
            self.stdout.write(self.style.WARNING("No assistant_messages table found"))
            return
        
        count = 0
        for row in rows:
            if dry_run:
                self.stdout.write(f"  Would migrate message: {row['id']}")
            else:
                if not Message.objects.filter(id=row["id"]).exists():
                    # Get or skip if conversation doesn't exist
                    try:
                        conversation = Conversation.objects.get(id=row["conversation_id"])
                    except Conversation.DoesNotExist:
                        continue
                    
                    Message.objects.create(
                        id=row["id"],
                        conversation=conversation,
                        role=row["role"],
                        content=row.get("content", ""),
                        tool_calls=row.get("tool_calls"),
                        tool_call_id=row.get("tool_call_id", ""),
                        name=row.get("name", ""),
                        tokens_used=row.get("tokens_used", 0),
                    )
                    count += 1
        
        self.stdout.write(f"  Migrated {count} messages")
    
    def _migrate_action_logs(self, cursor, dry_run):
        """Migrate assistant_action_logs table."""
        self.stdout.write("Migrating action logs...")
        
        try:
            cursor.execute("SELECT * FROM assistant_action_logs")
            rows = cursor.fetchall()
        except sqlite3.OperationalError:
            self.stdout.write(self.style.WARNING("No assistant_action_logs table found"))
            return
        
        count = 0
        for row in rows:
            if dry_run:
                self.stdout.write(f"  Would migrate action log: {row['id']}")
            else:
                if not ActionLog.objects.filter(id=row["id"]).exists():
                    conversation = None
                    if row.get("conversation_id"):
                        try:
                            conversation = Conversation.objects.get(id=row["conversation_id"])
                        except Conversation.DoesNotExist:
                            pass
                    
                    ActionLog.objects.create(
                        id=row["id"],
                        conversation=conversation,
                        action_name=row["action_name"],
                        action_type=row["action_type"],
                        parameters=row.get("parameters", {}),
                        result=row.get("result"),
                        status=row.get("status", "pending"),
                        confirmation_id=row.get("confirmation_id", ""),
                        user_id=row.get("user_id", ""),
                        error_message=row.get("error_message", ""),
                    )
                    count += 1
        
        self.stdout.write(f"  Migrated {count} action logs")

