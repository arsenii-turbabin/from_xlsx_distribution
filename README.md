# Mailing Import Service

Django service for importing mailing records from XLSX files and asynchronous email delivery.

## Stack

* Python 3.12
* Django 4.2
* Celery
* Redis
* SQLite
* OpenPyXL
* unittest

## Features

* XLSX import via Django Management Command
* Idempotent processing using `external_id`
* Bulk database inserts (`bulk_create`)
* Asynchronous email delivery with Celery
* Delivery statuses (`PENDING`, `SENT`, `FAILED`)
* Automatic task retries
* Test coverage

## Input File Format

The first row must contain headers:

| Column      | Description                          |
| ----------- | ------------------------------------ |
| external_id | Unique identifier in external system |
| user_id     | User identifier                      |
| email       | Recipient email                      |
| subject     | Email subject                        |
| message     | Email body                           |

Example:

| external_id | user_id | email                                         | subject | message         |
| ----------- | ------- | --------------------------------------------- | ------- | --------------- |
| ext-1       | u1      | [user1@example.com](mailto:user1@example.com) | Hello   | Test message    |
| ext-2       | u2      | [user2@example.com](mailto:user2@example.com) | Hi      | Another message |

## Quick Start

```bash
# 1. Clone repository
git clone <repo>
cd mailing_service

# 2. Create virtual environment
python -m venv .venv

source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Apply migrations
python manage.py migrate
```

## Run Redis

```bash
docker run -d --name redis -p 6379:6379 redis:7
```

## Run Celery Worker

```bash
celery -A config worker -l info
```

## Import Mailing File

```bash
python manage.py import_mailing sample_data.xlsx
```

Example output:

```text
Import completed

Processed rows: 100
Created records: 95
Skipped records: 3
Error rows: 2
```

## Verify Celery Processing

After running the import command, switch to the terminal where the Celery worker is running.

You should see messages similar to:

```text
Task mailing.tasks.send_email_task[...] received

EMAIL SENT | id=1 | email=user1@example.com

Task mailing.tasks.send_email_task[...] succeeded

## Email Delivery

Email sending is simulated according to the task requirements:

```python
sleep(randint(5, 20))
```

Each successfully processed record is queued to Celery and delivered asynchronously.

## Tests

Run all tests:

```bash
python manage.py test
```

Run mailing tests only:

```bash
python manage.py test mailing
```

Tests do not require Redis or a running Celery worker.

## Architecture

```text
XLSX
  │
  ▼
Management Command
  │
  ▼
MailingRecord
  │
  ▼
Celery
  │
  ▼
Redis
  │
  ▼
Worker
  │
  ▼
Email Delivery (simulated)
```
