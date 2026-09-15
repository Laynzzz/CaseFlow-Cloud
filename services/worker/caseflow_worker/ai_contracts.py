"""Model output is a proposal. Ordinary code validates structure, spans and arithmetic."""
from decimal import Decimal, ROUND_HALF_UP
import re
from pydantic import BaseModel, ConfigDict, Field
from typing import Annotated

SCHEMA_VERSION = "purchase-assistant-v3"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Citation(StrictModel):
    chunkId: str
    quote: str = Field(min_length=1, max_length=1200)


class TextSuggestion(StrictModel):
    value: str | None
    citations: list[Citation]


class CurrencySuggestion(TextSuggestion):
    value: Annotated[str, Field(pattern=r"^[A-Z]{3}$", description="Three-letter currency code only, for example USD.")] | None


class AmountSuggestion(TextSuggestion):
    value: Annotated[str, Field(pattern=r"^[0-9]{1,12}(\.[0-9]{1,4})?$", description="Decimal amount only, without currency, commas or symbols; for example 4200.00.")] | None


class LineItem(StrictModel):
    description: str = Field(min_length=1, max_length=500)
    quantity: str = Field(pattern=r"^[0-9]{1,10}(\.[0-9]{1,3})?$")
    unitPrice: str = Field(pattern=r"^[0-9]{1,12}(\.[0-9]{1,4})?$")


class ItemSuggestion(StrictModel):
    value: list[LineItem] | None
    citations: list[Citation]


class Extraction(StrictModel):
    vendor: TextSuggestion
    currency: CurrencySuggestion
    total: AmountSuggestion
    lineItems: ItemSuggestion
    warnings: list[str]


class Finding(StrictModel):
    claim: str = Field(min_length=1,max_length=2000)
    citations: list[Citation] = Field(min_length=1,max_length=10)


class Review(StrictModel):
    summary: str = Field(max_length=2000)
    missing_information: list[str] = Field(max_length=20)
    policy_findings: list[Finding] = Field(max_length=20)
    citations: list[Citation] = Field(max_length=50)
    insufficient_evidence: bool


def validate_citations(citations, chunks):
    """Only an already-authorized retrieved chunk can resolve. Never fetch arbitrary IDs."""
    resolved = []
    for citation in citations:
        chunk = chunks.get(citation.chunkId)
        if chunk is None or citation.quote not in chunk["text"]:
            raise ValueError("INVALID_CITATION")
        start = chunk["start"] + chunk["text"].index(citation.quote)
        resolved.append(dict(chunkId=citation.chunkId, sourceId=chunk["sourceId"], page=chunk["page"],
                             start=start, end=start+len(citation.quote), quote=citation.quote))
    return resolved


def validate_extraction(result: Extraction, chunks):
    for field in (result.vendor,result.currency,result.total,result.lineItems):
        validate_citations(field.citations, chunks)
        if field.value is not None and not field.citations:
            raise ValueError("UNSOURCED_EXTRACTION")
    if result.vendor.value is not None and not 1 <= len(result.vendor.value) <= 200:
        raise ValueError("INVALID_VENDOR")
    currency = result.currency.value
    if currency is not None and not re.fullmatch(r"[A-Z]{3}", currency):
        raise ValueError("INVALID_CURRENCY")
    items = result.lineItems.value
    total = result.total.value
    if items is not None:
        if not 1 <= len(items) <= 100:
            raise ValueError("INVALID_LINE_ITEMS")
        for item in items:
            if not re.fullmatch(r"[0-9]{1,10}(\.[0-9]{1,3})?", item.quantity) or Decimal(item.quantity) <= 0:
                raise ValueError("INVALID_QUANTITY")
            if not re.fullmatch(r"[0-9]{1,12}(\.[0-9]{1,4})?", item.unitPrice):
                raise ValueError("INVALID_UNIT_PRICE")
    if total is not None and not re.fullmatch(r"[0-9]{1,12}(\.[0-9]{1,4})?", total):
        raise ValueError("INVALID_TOTAL")
    # Freeze the initial AI currency scope; Java remains the authority on acceptance.
    decimals = {"USD":2,"EUR":2,"GBP":2,"CAD":2,"AUD":2,"JPY":0,"KWD":3}
    if currency is not None and currency not in decimals:
        raise ValueError("AI_CURRENCY_UNSUPPORTED")
    if items and total is not None and currency:
        unit = Decimal(1).scaleb(-decimals[currency])
        computed = sum((Decimal(i.quantity)*Decimal(i.unitPrice)).quantize(unit,rounding=ROUND_HALF_UP) for i in items)
        if computed != Decimal(total):
            raise ValueError("INCONSISTENT_TOTAL")
    return result


def validate_review(result: Review, chunks):
    validate_citations(result.citations, chunks)
    for finding in result.policy_findings:
        validate_citations(finding.citations, chunks)
    if not chunks and (not result.insufficient_evidence or result.policy_findings):
        raise ValueError("EXPECTED_ABSTENTION")
    if result.policy_findings and not result.citations:
        raise ValueError("UNSOURCED_REVIEW")
    return result
