import shutil
from pathlib import Path

import pytest

from ocr_agent import pdf_has_text, process_file, MissingDependencyError

TEXT_PDF = b"""%PDF-1.1
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj
4 0 obj
<< /Length 55 >>
stream
BT
/F1 24 Tf
72 720 Td
(Hello, World!) Tj
ET
endstream
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
xref
0 6
0000000000 65535 f 
0000000010 00000 n 
0000000053 00000 n 
0000000103 00000 n 
0000000207 00000 n 
0000000283 00000 n 
trailer
<< /Root 1 0 R /Size 6 >>
startxref
354
%%EOF
"""

IMAGE_PDF = b"""%PDF-1.1
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>
endobj
xref
0 4
0000000000 65535 f 
0000000010 00000 n 
0000000053 00000 n 
0000000103 00000 n 
trailer
<< /Root 1 0 R /Size 4 >>
startxref
152
%%EOF
"""


def write_pdf(path: Path, content: bytes) -> Path:
    path.write_bytes(content)
    return path


def test_pdf_has_text(tmp_path: Path) -> None:
    text_pdf = write_pdf(tmp_path / "text.pdf", TEXT_PDF)
    image_pdf = write_pdf(tmp_path / "image.pdf", IMAGE_PDF)
    assert pdf_has_text(text_pdf) is True
    assert pdf_has_text(image_pdf) is False


def test_missing_tesseract(tmp_path: Path, monkeypatch) -> None:
    pdf = write_pdf(tmp_path / "scan.pdf", IMAGE_PDF)

    def fake_which(name: str) -> None:
        return None

    monkeypatch.setattr(shutil, "which", fake_which)
    with pytest.raises(MissingDependencyError):
        process_file(pdf, tmp_path / "out.pdf", "eng", 1, False)
