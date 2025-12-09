#!/usr/bin/env python3
"""Check UniFi secrets on remote server."""
from database import decrypt_value, get_db, Secret

def main():
    db = next(get_db())
    try:
        secrets = db.query(Secret).filter(Secret.service_type == 'unifi').all()
        if secrets:
            print("UniFi secrets:")
            for s in secrets:
                try:
                    value = decrypt_value(s.encrypted_value)
                    print(f"  {s.key}: {value}")
                except Exception as e:
                    print(f"  {s.key}: [decrypt error: {e}]")
        else:
            print("No UniFi secrets found")
    finally:
        db.close()

if __name__ == '__main__':
    main()


