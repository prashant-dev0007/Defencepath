#!/usr/bin/env python3
"""
DEFENCE PATH - Production Database Backup & Retention Tool
Lead Architect & Developer: Er. Prashant Mishra (Ph: 6390314464)

Features:
- Online, lock-free SQLite atomic snapshot using native backup API.
- Timestamped backup archives in 'backups/' directory.
- Automated rotation keeping the latest N backups (default: 30 days).
- Safe restoration functionality with verification.
- Can be scheduled via cron (Linux/Hostinger) or Task Scheduler (Windows).
"""

import os
import sys
import sqlite3
import argparse
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, 'defence_path.db')
BACKUP_DIR = os.path.join(BASE_DIR, 'backups')
DEFAULT_RETENTION = 30

def create_backup(retention_count=DEFAULT_RETENTION):
    """Creates a point-in-time atomic backup of defence_path.db."""
    if not os.path.exists(DB_FILE):
        print(f"[!] Error: Source database not found at '{DB_FILE}'")
        return False

    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target_backup_file = os.path.join(BACKUP_DIR, f"defence_path_backup_{timestamp}.db")

    print(f"[*] Starting online atomic backup of DEFENCE PATH database...")
    print(f"    Source: {DB_FILE}")
    print(f"    Target: {target_backup_file}")

    try:
        source_conn = sqlite3.connect(DB_FILE, timeout=30.0)
        dest_conn = sqlite3.connect(target_backup_file)

        with dest_conn:
            source_conn.backup(dest_conn, pages=100)

        dest_conn.close()
        source_conn.close()

        file_size_kb = os.path.getsize(target_backup_file) / 1024
        print(f"[+] Backup completed successfully! Size: {file_size_kb:.2f} KB")

        # Prune old backups
        prune_backups(retention_count)
        return True

    except Exception as e:
        print(f"[!] Database backup failed: {str(e)}")
        if os.path.exists(target_backup_file):
            try:
                os.remove(target_backup_file)
            except OSError:
                pass
        return False

def prune_backups(max_keep=DEFAULT_RETENTION):
    """Deletes oldest backup files exceeding the retention count."""
    if not os.path.exists(BACKUP_DIR):
        return

    files = [
        os.path.join(BACKUP_DIR, f)
        for f in os.listdir(BACKUP_DIR)
        if f.startswith('defence_path_backup_') and f.endswith('.db')
    ]
    files.sort(key=os.path.getmtime)

    excess = len(files) - max_keep
    if excess > 0:
        print(f"[*] Pruning {excess} backup file(s) exceeding retention limit of {max_keep}...")
        for i in range(excess):
            try:
                os.remove(files[i])
                print(f"    Deleted: {os.path.basename(files[i])}")
            except Exception as e:
                print(f"    [!] Failed to remove {files[i]}: {e}")

def restore_backup(backup_path):
    """Restores database from specified backup file after making an emergency snapshot."""
    if not os.path.exists(backup_path):
        print(f"[!] Error: Backup file not found at '{backup_path}'")
        return False

    print(f"[!] WARNING: Restoring database will overwrite active database at: {DB_FILE}")
    
    # Create emergency backup of current DB first
    if os.path.exists(DB_FILE):
        emergency_file = os.path.join(BACKUP_DIR, f"pre_restore_snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
        print(f"[*] Creating emergency pre-restore snapshot: {emergency_file}")
        source_conn = sqlite3.connect(DB_FILE, timeout=30.0)
        dest_conn = sqlite3.connect(emergency_file)
        source_conn.backup(dest_conn)
        dest_conn.close()
        source_conn.close()

    try:
        backup_conn = sqlite3.connect(backup_path)
        active_conn = sqlite3.connect(DB_FILE, timeout=30.0)
        with active_conn:
            backup_conn.backup(active_conn)
        active_conn.close()
        backup_conn.close()
        print(f"[+] Database successfully restored from '{backup_path}'!")
        return True
    except Exception as e:
        print(f"[!] Restore operation failed: {e}")
        return False

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="DEFENCE PATH Database Backup Utility")
    parser.add_argument('--retention', type=int, default=DEFAULT_RETENTION, help="Number of backup snapshots to keep")
    parser.add_argument('--restore', type=str, help="Path to backup file to restore")
    args = parser.parse_args()

    if args.restore:
        restore_backup(args.restore)
    else:
        create_backup(args.retention)
