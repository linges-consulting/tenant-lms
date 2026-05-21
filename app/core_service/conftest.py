# Root conftest.py — loaded by pytest before any test/test-conftest files.
# Mocks weasyprint so that tests can run locally without the native GObject/Pango
# libraries that WeasyPrint requires (which are only available inside Docker).
import sys
from unittest.mock import MagicMock

_wp = MagicMock()
_wp.HTML.return_value.write_pdf.return_value = b"%PDF-mock"
sys.modules.setdefault("weasyprint", _wp)
