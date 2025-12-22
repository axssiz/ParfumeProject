#!/usr/bin/env python3
"""
backup_db.py

Создаёт резервную копию PostgreSQL с помощью pg_dump (через subprocess).
- Сохраняет дамп в .sql (plain text) файл с датой/временем в имени.
- Автоматически создаёт папку для бэкапов, если её нет.
- Удаляет бэкапы старше 7 дней (ротация).

Пример использования:
  PGPASSWORD=yourpass python scripts/backup_db.py --db perfume_db --user postgres --host localhost

Примечание по безопасности:
  Не храните пароль в скрипте. Рекомендуется использовать переменную окружения PGPASSWORD
  или файл ~/.pgpass с корректными правами доступа.

Автор: ваш бэкап-скрипт
"""

import argparse
import os
import subprocess
import sys
from datetime import datetime, timedelta


def ensure_backup_dir(path):
    
    os.makedirs(path, exist_ok=True)


def dump_database(host, user, db, out_file):
    
    pg_dump = 'pg_dump'
   
    cmd = [pg_dump, '-h', host, '-U', user, '-F', 'p', '-f', out_file, db]
    print('Running:', ' '.join(cmd))
    try:
        
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
    except subprocess.CalledProcessError as e:
        print('pg_dump failed:', e.stderr if e.stderr else e, file=sys.stderr)
        raise


def rotate_backups(dir_path, keep_days=7, pattern_prefix=None):
   
    cutoff = datetime.now() - timedelta(days=keep_days)
    removed = []
    for fname in os.listdir(dir_path):
        if pattern_prefix and not fname.startswith(pattern_prefix):
            continue
        full = os.path.join(dir_path, fname)
        if not os.path.isfile(full):
            continue
        try:
            mtime = datetime.fromtimestamp(os.path.getmtime(full))
            if mtime < cutoff:
                os.remove(full)
                removed.append(full)
        except Exception as e:
            print('Rotation error for', full, e, file=sys.stderr)
    return removed


def main():
    parser = argparse.ArgumentParser(description='Postgres backup script using pg_dump')
    parser.add_argument('--host', default=os.getenv('PGHOST', 'localhost'))
    parser.add_argument('--db', required=True, help='Database name')
    parser.add_argument('--user', default=os.getenv('PGUSER', 'postgres'))
    parser.add_argument('--outdir', default=os.path.join(os.path.dirname(__file__), '..', 'backups'))
    parser.add_argument('--keep-days', type=int, default=7, help='Number of days to keep backups')

    args = parser.parse_args()

    outdir = os.path.abspath(args.outdir)
    ensure_backup_dir(outdir)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{args.db}_{timestamp}.sql"
    out_path = os.path.join(outdir, filename)

    print('Backup directory:', outdir)
    print('Output file:', out_path)

    try:
        dump_database(args.host, args.user, args.db, out_path)
        print('Backup completed:', out_path)
    except Exception as e:
        print('Backup failed:', e, file=sys.stderr)
        sys.exit(2)

    # rotate old backups
    removed = rotate_backups(outdir, keep_days=args.keep_days, pattern_prefix=f"{args.db}_")
    if removed:
        print('Removed old backups:')
        for r in removed:
            print(' -', r)


if __name__ == '__main__':
    main()
