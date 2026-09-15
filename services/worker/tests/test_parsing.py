import hashlib
import io
import pytest
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
from caseflow_worker.parsing import parse, isolated_parse


def pdf(text=None, pages=1, password=None):
    writer = PdfWriter()
    for _ in range(pages):
        page = writer.add_blank_page(612, 792)
        if text:
            font = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
                                     NameObject("/Subtype"): NameObject("/Type1"),
                                     NameObject("/BaseFont"): NameObject("/Helvetica")})
            page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
            stream = DecodedStreamObject()
            stream.set_data(f"BT /F1 12 Tf 20 700 Td ({text}) Tj ET".encode())
            page[NameObject("/Contents")] = writer._add_object(stream)
    if password:
        writer.encrypt(password)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def test_text_offsets_and_hashes_preserve_unicode():
    data = ("Policy café\r\n" + "equipment costs " * 110 + "\fSecond page").encode()
    result = isolated_parse(data, "text/plain")
    assert result["pageCount"] == 2
    assert result["sourceSha256"] == hashlib.sha256(data).hexdigest()
    assert len(result["chunks"]) >= 3
    for chunk in result["chunks"]:
        assert result["pages"][chunk["page"]-1][chunk["start"]:chunk["end"]] == chunk["text"]
        assert hashlib.sha256(chunk["text"].encode()).hexdigest() == chunk["sha256"]


def test_pdf_child_extracts_text():
    result = isolated_parse(pdf("Synthetic vendor quote USD 4200"), "application/pdf")
    assert "USD 4200" in result["chunks"][0]["text"]
    assert result["parserVersion"] == "pypdf-6.18.1+utf8-v1"


@pytest.mark.parametrize("data,media,code", [
    (b"", "text/plain", "SOURCE_SIZE_LIMIT"),
    (b"x" * (10*1024*1024+1), "text/plain", "SOURCE_SIZE_LIMIT"),
    (b"\xff", "text/plain", "INVALID_UTF8"),
    (b"x\x00y", "text/plain", "BINARY_TEXT_UNSUPPORTED"),
    (b"x", "image/png", "UNSUPPORTED_SOURCE_TYPE"),
    (b"bad", "application/pdf", "MALFORMED_PDF"),
    (b"%PDF-bad", "application/pdf", "MALFORMED_PDF"),
    (b" \n", "text/plain", "NO_EXTRACTABLE_TEXT"),
    (b"page\f"*50, "text/plain", "SOURCE_PAGE_LIMIT"),
    (b"x"*1_000_001, "text/plain", "SOURCE_TEXT_LIMIT"),
], ids=["empty", "oversize", "utf8", "binary", "media", "header", "malformed", "blank", "pages", "text-size"])
def test_reject_unsupported_input(data, media, code):
    with pytest.raises(ValueError, match=code):
        isolated_parse(data, media)


def test_pdf_rejections():
    for data, code in [(pdf(), "NO_EXTRACTABLE_TEXT"), (pdf(pages=51), "SOURCE_PAGE_LIMIT"),
                       (pdf("secret", password="synthetic"), "ENCRYPTED_PDF_UNSUPPORTED")]:
        with pytest.raises(ValueError, match=code):
            isolated_parse(data, "application/pdf")
