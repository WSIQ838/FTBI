from unittest.mock import patch
from django.test import SimpleTestCase,override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from academics.attachment_views import AttachmentForm

class ScanningTests(SimpleTestCase):
    @override_settings(FTBI_CLAMAV_HOST="")
    def test_document_disabled_without_scanner(self):
        form=AttachmentForm({},{"file":SimpleUploadedFile("a.pdf",b"%PDF-1.4\nTest")})
        self.assertFalse(form.is_valid())
    @override_settings(FTBI_CLAMAV_HOST="scanner")
    @patch("academics.attachment_views.scan_clean",return_value=False)
    def test_scanner_failure_rejects(self,scan):
        form=AttachmentForm({},{"file":SimpleUploadedFile("a.pdf",b"%PDF-1.4\nTest")})
        self.assertFalse(form.is_valid())
        scan.assert_called_once()
    @override_settings(FTBI_CLAMAV_HOST="scanner")
    @patch("academics.attachment_views.scan_clean",return_value=True)
    def test_clean_pdf_allowed(self,scan):
        self.assertTrue(AttachmentForm({},{"file":SimpleUploadedFile("a.pdf",b"%PDF-1.4\nTest")}).is_valid())
