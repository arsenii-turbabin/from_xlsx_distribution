import argparse
import logging
from typing import Any

import openpyxl
from django.core.management.base import BaseCommand, CommandError

from mailing.models import MailingRecord
from mailing.tasks import send_email_task

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = {
    "external_id",
    "user_id",
    "email",
    "subject",
    "message",
}


class Command(BaseCommand):
    help = "Import mailing records from XLSX."

    def add_arguments(
        self,
        parser: argparse.ArgumentParser,
    ) -> None:
        parser.add_argument(
            "file_path",
            type=str,
        )

    def handle(
        self,
        *args: Any,
        **options: Any,
    ) -> None:
        file_path = options["file_path"]

        try:
            workbook = openpyxl.load_workbook(
                file_path,
                read_only=True,
            )
        except FileNotFoundError:
            raise CommandError(
                f"File not found: {file_path}"
            )

        except Exception as exc:
            raise CommandError(
                f"Unable to open XLSX file: {exc}"
            )

        worksheet = workbook.active
        if worksheet is None:
            raise CommandError(
                "Worksheet not found."
            )

        rows_iter = worksheet.iter_rows(
            values_only=True
        )

        try:
            raw_headers = next(rows_iter)
        except StopIteration:
            raise CommandError(
                "File is empty."
            )

        headers = [
            str(value).strip().lower()
            if value is not None
            else ""
            for value in raw_headers
        ]

        missing_columns = (REQUIRED_COLUMNS - set(headers))
        if missing_columns:
            raise CommandError(
                "Missing columns: "
                + ", ".join(
                    sorted(missing_columns)
                )
            )

        column_map = {
            name: idx
            for idx, name in enumerate(headers)
        }

        processed = 0
        created = 0
        skipped = 0
        errors = 0

        records = []

        external_ids = []

        for row_index, row in enumerate(rows_iter, start=2):
            processed += 1

            try:
                external_id = self._cell(
                    row,
                    column_map["external_id"],
                )
                user_id = self._cell(
                    row,
                    column_map["user_id"],
                )
                email = self._cell(
                    row,
                    column_map["email"],
                )
                subject = self._cell(
                    row,
                    column_map["subject"],
                )
                message = self._cell(
                    row,
                    column_map["message"],
                )

                if not external_id:
                    raise ValueError(
                        "external_id is empty"
                    )
                if not email:
                    raise ValueError(
                        "email is empty"
                    )

                external_ids.append(
                    external_id
                )
                records.append(
                    MailingRecord(
                        external_id=external_id,
                        user_id=user_id,
                        email=email,
                        subject=subject,
                        message=message,
                    )
                )

            except Exception as exc:
                logger.warning(
                    "Row %s error: %s",
                    row_index,
                    exc,
                )
                errors += 1

        existing_external_ids = set(
            MailingRecord.objects.filter(
                external_id__in=external_ids
            ).values_list(
                "external_id",
                flat=True,
            )
        )

        new_records = [
            record
            for record in records
            if record.external_id
            not in existing_external_ids
        ]

        skipped = (
            len(records)
            - len(new_records)
        )

        created_records = (
            MailingRecord.objects.bulk_create(
                new_records,
                batch_size=1000,
            )
        )
        created = len(created_records)
        for record in created_records:
            send_email_task.delay(record.pk)

        result = (
            "\nImport completed\n"
            f"Processed rows: {processed}\n"
            f"Created records: {created}\n"
            f"Skipped records: {skipped}\n"
            f"Error rows: {errors}\n"
        )

        self.stdout.write(result)

    @staticmethod
    def _cell(
        row: tuple[Any, ...],
        index: int,
    ) -> str:
        try:
            value = row[index]
        except IndexError:
            return ""

        if value is None:
            return ""

        return str(value).strip()
