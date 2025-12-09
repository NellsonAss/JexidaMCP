#!/usr/bin/env python3
"""Check secrets in the old FastAPI database."""
import sqlite3

def main():
    conn = sqlite3.connect('/opt/jexida-mcp/secrets.db')
    cursor = conn.cursor()
    
    # Get all tables
    tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    print('Tables in secrets.db:')
    for (table,) in tables:
        count = cursor.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
        print(f'  {table}: {count} rows')
        
        # Show columns
        cols = cursor.execute(f'PRAGMA table_info({table})').fetchall()
        col_names = [c[1] for c in cols]
        print(f'    Columns: {col_names}')
        
        # Show sample data if not too many rows
        if count > 0 and count < 50:
            rows = cursor.execute(f'SELECT * FROM {table} LIMIT 5').fetchall()
            for row in rows:
                # Truncate long values
                display = []
                for i, val in enumerate(row):
                    if isinstance(val, str) and len(val) > 50:
                        display.append(f'{col_names[i]}={val[:50]}...')
                    else:
                        display.append(f'{col_names[i]}={val}')
                print(f'      {display}')
    
    conn.close()

if __name__ == '__main__':
    main()


