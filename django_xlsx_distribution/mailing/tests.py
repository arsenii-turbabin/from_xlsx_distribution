import io
import os
import tempfile
from unittest.mock import patch

import openpyxl
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from mailing.models import MailingRecord


def _create_xlsx(headers: list[str], rows: list[list[str | None]]) -> bytes:
    """Create an in-memory XLSX file and return its bytes."""
    workbook = openpyxl.Workbook()
    worksheet = workbook.active

    worksheet.append(headers)

    for row in rows:
        worksheet.append(row)

    buffer = io.BytesIO()

    workbook.save(buffer)

    buffer.seek(0)

    return buffer.read()


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
)
class ImportMailingCommandTest(TestCase):
    """Integration tests for import_mailing command."""

    def _run_import(self, xlsx_bytes: bytes) -> str:
        with tempfile.NamedTemporaryFile(
            suffix=".xlsx",
            delete=False,
        ) as temp_file:
            temp_file.write(xlsx_bytes)
            temp_path = temp_file.name

        try:
            stdout = io.StringIO()

            call_command(
                "import_mailing",
                temp_path,
                stdout=stdout,
            )

            return stdout.getvalue()

        finally:
            os.unlink(temp_path)

    @patch(
        "mailing.management.commands.import_mailing.send_email_task.delay"
    )
    def test_successful_import(
        self,
        mock_delay,
    ):
        xlsx = _create_xlsx(
            headers=[
                "external_id",
                "user_id",
                "email",
                "subject",
                "message",
            ],
            rows=[
                [
                    "ext-1",
                    "u1",
                    "alice@example.com",
                    "Hello",
                    "Body A",
                ],
                [
                    "ext-2",
                    "u2",
                    "bob@example.com",
                    "Hi",
                    "Body B",
                ],
            ],
        )

        output = self._run_import(xlsx)

        self.assertIn("Processed rows: 2", output)
        self.assertIn("Created records: 2", output)
        self.assertIn("Skipped records: 0", output)
        self.assertIn("Error rows: 0", output)

        self.assertEqual(
            MailingRecord.objects.count(),
            2,
        )

        self.assertEqual(
            mock_delay.call_count,
            2,
        )

        record = MailingRecord.objects.get(
            external_id="ext-1"
        )

        self.assertEqual(
            record.email,
            "alice@example.com",
        )

        self.assertEqual(
            record.subject,
            "Hello",
        )

        self.assertEqual(
            record.status,
            MailingRecord.Status.PENDING,
        )

    @patch(
        "mailing.management.commands.import_mailing.send_email_task.delay"
    )
    def test_idempotency_skips_duplicate_external_id(
        self,
        mock_delay,
    ):
        MailingRecord.objects.create(
            external_id="ext-1",
            user_id="u1",
            email="alice@example.com",
            subject="Hello",
            message="Body A",
        )

        xlsx = _create_xlsx(
            headers=[
                "external_id",
                "user_id",
                "email",
                "subject",
                "message",
            ],
            rows=[
                [
                    "ext-1",
                    "u1",
                    "alice@example.com",
                    "Hello",
                    "Body A",
                ],
                [
                    "ext-2",
                    "u2",
                    "bob@example.com",
                    "Hi",
                    "Body B",
                ],
            ],
        )

        output = self._run_import(xlsx)

        self.assertIn("Processed rows: 2", output)
        self.assertIn("Created records: 1", output)
        self.assertIn("Skipped records: 1", output)
        self.assertIn("Error rows: 0", output)

        self.assertEqual(
            MailingRecord.objects.count(),
            2,
        )

        self.assertEqual(
            mock_delay.call_count,
            1,
        )

    @patch(
        "mailing.management.commands.import_mailing.send_email_task.delay"
    )
    def test_missing_external_id_is_an_error(
        self,
        mock_delay,
    ):
        xlsx = _create_xlsx(
            headers=[
                "external_id",
                "user_id",
                "email",
                "subject",
                "message",
            ],
            rows=[
                [
                    "",
                    "u1",
                    "alice@example.com",
                    "Hello",
                    "Body A",
                ],
                [
                    "ext-2",
                    "u2",
                    "bob@example.com",
                    "Hi",
                    "Body B",
                ],
            ],
        )

        output = self._run_import(xlsx)

        self.assertIn("Processed rows: 2", output)
        self.assertIn("Created records: 1", output)
        self.assertIn("Skipped records: 0", output)
        self.assertIn("Error rows: 1", output)

        self.assertEqual(
            mock_delay.call_count,
            1,
        )

    @patch(
        "mailing.management.commands.import_mailing.send_email_task.delay"
    )
    def test_missing_email_is_an_error(
        self,
        mock_delay,
    ):
        xlsx = _create_xlsx(
            headers=[
                "external_id",
                "user_id",
                "email",
                "subject",
                "message",
            ],
            rows=[
                [
                    "ext-1",
                    "u1",
                    "",
                    "Hello",
                    "Body A",
                ],
            ],
        )

        output = self._run_import(xlsx)

        self.assertIn("Processed rows: 1", output)
        self.assertIn("Created records: 0", output)
        self.assertIn("Error rows: 1", output)

        self.assertEqual(
            mock_delay.call_count,
            0,
        )

    def test_missing_columns_raises_error(self):
        xlsx = _create_xlsx(
            headers=[
                "external_id",
                "user_id",
            ],
            rows=[
                [
                    "ext-1",
                    "u1",
                ],
            ],
        )

        with tempfile.NamedTemporaryFile(
            suffix=".xlsx",
            delete=False,
        ) as temp_file:
            temp_file.write(xlsx)
            temp_path = temp_file.name

        try:
            with self.assertRaises(
                CommandError
            ) as context:
                call_command(
                    "import_mailing",
                    temp_path,
                )

            self.assertIn(
                "Missing columns",
                str(context.exception),
            )

        finally:
            os.unlink(temp_path)

    def test_empty_file(self):
        xlsx = _create_xlsx(
            headers=[
                "external_id",
                "user_id",
                "email",
                "subject",
                "message",
            ],
            rows=[],
        )

        output = self._run_import(xlsx)

        self.assertIn(
            "Processed rows: 0",
            output,
        )

        self.assertIn(
            "Created records: 0",
            output,
        )

    def test_file_not_found_raises_error(self):
        with self.assertRaises(
            CommandError
        ) as context:
            call_command(
                "import_mailing",
                "/nonexistent/file.xlsx",
            )

        self.assertIn(
            "File not found",
            str(context.exception),
        )

    @patch(
        "mailing.management.commands.import_mailing.send_email_task.delay"
    )
    def test_column_order_is_flexible(
        self,
        mock_delay,
    ):
        xlsx = _create_xlsx(
            headers=[
                "email",
                "external_id",
                "message",
                "subject",
                "user_id",
            ],
            rows=[
                [
                    "alice@example.com",
                    "ext-1",
                    "Body A",
                    "Hello",
                    "u1",
                ],
            ],
        )

        output = self._run_import(xlsx)

        self.assertIn(
            "Created records: 1",
            output,
        )

        self.assertIn(
            "Error rows: 0",
            output,
        )

        record = MailingRecord.objects.get(
            external_id="ext-1",
        )

        self.assertEqual(
            record.email,
            "alice@example.com",
        )

        self.assertEqual(
            mock_delay.call_count,
            1,
        )

    @patch(
        "mailing.management.commands.import_mailing.send_email_task.delay"
    )
    def test_extra_columns_are_ignored(
        self,
        mock_delay,
    ):
        xlsx = _create_xlsx(
            headers=[
                "external_id",
                "user_id",
                "email",
                "subject",
                "message",
                "extra_column",
            ],
            rows=[
                [
                    "ext-1",
                    "u1",
                    "alice@example.com",
                    "Hello",
                    "Body A",
                    "ignored",
                ],
            ],
        )

        output = self._run_import(xlsx)

        self.assertIn(
            "Created records: 1",
            output,
        )

        self.assertIn(
            "Error rows: 0",
            output,
        )

        self.assertEqual(
            mock_delay.call_count,
            1,
        )

    @patch(
        "mailing.management.commands.import_mailing.send_email_task.delay"
    )
    def test_task_is_queued_for_each_new_record(
        self,
        mock_delay,
    ):
        xlsx = _create_xlsx(
            headers=[
                "external_id",
                "user_id",
                "email",
                "subject",
                "message",
            ],
            rows=[
                [
                    "ext-1",
                    "u1",
                    "alice@example.com",
                    "Hello",
                    "Body A",
                ],
                [
                    "ext-2",
                    "u2",
                    "bob@example.com",
                    "Hi",
                    "Body B",
                ],
            ],
        )

        self._run_import(xlsx)

        self.assertEqual(
            mock_delay.call_count,
            2,
        )
