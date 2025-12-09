#!/usr/bin/env python3
"""Migrate secrets from old FastAPI database to Django database."""
import sqlite3
import os

OLD_DB = '/opt/jexida-mcp/secrets.db'
DJANGO_DB = '/opt/jexida-mcp/jexida_dashboard/db.sqlite3'

def migrate_secrets():
    """Copy secrets from old database to new Django database."""
    # Connect to both databases
    old_conn = sqlite3.connect(OLD_DB)
    old_conn.row_factory = sqlite3.Row
    new_conn = sqlite3.connect(DJANGO_DB)
    
    old_cursor = old_conn.cursor()
    new_cursor = new_conn.cursor()
    
    # Get secrets from old database
    old_cursor.execute('SELECT id, name, service_type, key, encrypted_value, created_at, updated_at FROM secrets')
    secrets = old_cursor.fetchall()
    
    print(f'Found {len(secrets)} secrets in old database')
    
    # The Django model has db_table = "secrets", same as original
    # Check what's in Django database
    new_cursor.execute('SELECT COUNT(*) FROM secrets')
    existing = new_cursor.fetchone()[0]
    print(f'Existing secrets in Django database: {existing}')
    
    if existing > 0:
        print('Django database already has secrets. Clearing first...')
        new_cursor.execute('DELETE FROM secrets')
        new_conn.commit()
    
    # Insert into Django database
    for secret in secrets:
        print(f'  Migrating: {secret["name"]} ({secret["service_type"]}/{secret["key"]})')
        new_cursor.execute('''
            INSERT INTO secrets (name, service_type, key, encrypted_value, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            secret['name'],
            secret['service_type'],
            secret['key'],
            secret['encrypted_value'],
            secret['created_at'],
            secret['updated_at']
        ))
    
    new_conn.commit()
    
    # Verify migration
    new_cursor.execute('SELECT COUNT(*) FROM secrets')
    migrated = new_cursor.fetchone()[0]
    print(f'\nMigration complete! {migrated} secrets in Django database')
    
    # Show migrated secrets
    new_cursor.execute('SELECT name, service_type, key FROM secrets')
    for row in new_cursor.fetchall():
        print(f'  - {row[0]} ({row[1]}/{row[2]})')
    
    old_conn.close()
    new_conn.close()

if __name__ == '__main__':
    migrate_secrets()

