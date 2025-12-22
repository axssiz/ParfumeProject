**Резервное копирование и восстановление базы данных (PostgreSQL)**

- **Файлы:**

  - [scripts/backup_db.ps1](scripts/backup_db.ps1) — PowerShell скрипт для Windows (создаёт .dump с помощью `pg_dump`).
  - [scripts/backup_db.sh](scripts/backup_db.sh) — Bash скрипт для Linux/macOS (создаёт gzip SQL дамп).
  - [scripts/restore_db.sh](scripts/restore_db.sh) — Скрипт восстановления из .sql.gz или .sql.
  - [scripts/migrations.sql](scripts/migrations.sql) — Базовая схема (CREATE TABLE IF NOT EXISTS).
  - [scripts/backup_task.xml](scripts/backup_task.xml) — Пример XML задачи для Task Scheduler (daily 03:00).
  - [scripts/backup_db.py](scripts/backup_db.py) — Python wrapper над `pg_dump` (кроссплатформенный).
  - [scripts/restore_db.py](scripts/restore_db.py) — Python wrapper для восстановления.
  - [scripts/migrate.py](scripts/migrate.py) — Запуск `scripts/migrations.sql` через `psycopg2` или `psql`.

- **Требования:**
  - Установленный `pg_dump`/`psql` (PostgreSQL client tools) в PATH.
  - Для автоматизации: PowerShell/Task Scheduler на Windows; `cron` на Linux.
  - (Опционально) `psycopg2` для `migrate.py`.

Настройка и использование (Python)

1. Установка пароля безопасно (рекомендуется использовать переменную окружения `PGPASSWORD`):

   В PowerShell (только текущая сессия):

   $env:PGPASSWORD = "your_postgres_password"

   В bash:

   export PGPASSWORD=yourpass

2. Ручный запуск Python бэкапа (по умолчанию custom .dump):

   ```bash
   python scripts/backup_db.py --db perfume_db --user postgres --host localhost
   # опции: --format custom|sqlgz|plain  --outdir /full/path/to/backups --keep 30
   ```

3. Восстановление через Python:

   ```bash
   python scripts/restore_db.py /full/path/to/perfume_db_20250101_030000.dump --db perfume_db --user postgres
   ```

4. Применение миграций (инициализация схемы):

   ```bash
   python scripts/migrate.py --db perfume_db --user postgres --host localhost
   ```

Автоматизация (Windows — Task Scheduler)

- Пример импорта XML: Откройте Task Scheduler > Import Task... > выберите `scripts/backup_task.xml` и убедитесь, что путь в `Arguments` указывает на Python-скрипт, например:

  `-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "C:\Users\User\Downloads\parfum (2) (1)\parfum\scripts\backup_db.py" --db perfume_db`

- Или зарегистрировать задачу из PowerShell (пример для Python):

````powershell
# Автоматический бэкап PostgreSQL (Python)

Этот репозиторий содержит скрипт `scripts/backup_db.py`, который создаёт резервные копии PostgreSQL с помощью `pg_dump` (через `subprocess`), сохраняет их в plain `.sql` файлы и автоматически удаляет бэкапы старше 7 дней.

Файлы:
- `scripts/backup_db.py` — Python-скрипт, соответствующий требованиям.

Требования:
- Python 3.8+
- Установленный `pg_dump` (PostgreSQL client tools) и доступность в `PATH`.

Установка зависимостей:
- Скрипт не требует внешних Python-пакетов.

Запуск вручную

1. Установите пароль в переменную окружения `PGPASSWORD` (рекомендуется):

PowerShell (только текущая сессия):

```powershell
$env:PGPASSWORD = "your_postgres_password"
````

Bash (Linux/macOS):

```bash
export PGPASSWORD=your_postgres_password
```

2. Запустите скрипт:

```bash
python scripts/backup_db.py --db perfume_db --user postgres --host localhost
```

- По умолчанию бэкапы сохраняются в `backups/` рядом с проектом.
- Имя файла: `perfume_db_YYYYMMDD_HHMMSS.sql`.
- По умолчанию сохраняются 7 дней; можно изменить через параметр `--keep-days`.

Пример с указанием директории и времени хранения:

```bash
python scripts/backup_db.py --db perfume_db --user postgres --host localhost --outdir /var/backups/perfume --keep-days 14
```

Автоматический запуск — cron (Linux)

Откройте crontab: `crontab -e` и добавьте строку для запуска ежедневно в 03:00:

```cron
0 3 * * * export PGPASSWORD=yourpass && /usr/bin/python3 /full/path/to/parfum/scripts/backup_db.py --db perfume_db --outdir /full/path/to/parfum/backups >> /var/log/parfum_backup.log 2>&1
```

Советы:

- Убедитесь, что `pg_dump` доступен в окружении cron. Иногда нужно добавить `PATH` в crontab или использовать полный путь к `pg_dump`.

Автоматический запуск — Task Scheduler (Windows)

1. Откройте Task Scheduler > Create Task...
2. Настройте Trigger (Daily 03:00).
3. В Actions укажите:
   - Program/script: полный путь к `python.exe` (например `C:\Python39\python.exe`)
   - Add arguments: `"C:\full\path\to\parfum\scripts\backup_db.py" --db perfume_db --outdir "C:\full\path\to\parfum\backups" --keep-days 7`

Примечания по безопасности

- Не храните пароль в скриптах или crontab в открытом виде. Используйте `PGPASSWORD` в окружении или `~/.pgpass` (Unix) с правами 600.
- На Windows рассмотрите безопасное хранилище для пароля.

Если хотите, могу зарегистрировать задачу в Task Scheduler автоматически (потребуются права администратора) или добавить сжатие бэкапов в `.gz`.
