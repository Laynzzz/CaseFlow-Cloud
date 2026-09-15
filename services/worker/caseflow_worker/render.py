import hashlib
from io import BytesIO
from uuid import uuid4
from docxtpl import DocxTemplate
from jinja2 import StrictUndefined
from jinja2.sandbox import SandboxedEnvironment
from .settings import BUCKET, storage

MAX_BYTES = 10 * 1024 * 1024


def context(snapshot):
    purchase = snapshot["purchase"]
    return dict(vendor=purchase["vendor"], description=purchase["description"], currency=purchase["currency"],
                total=purchase["total"], cost_center=purchase["costCenter"], justification=purchase["justification"],
                line_items="\n".join(f'{line["description"]}: {line["quantity"]} × {line["unitPrice"]}'
                                     for line in purchase["lineItems"]),
                approved_at=snapshot["approvedAt"], case_id=snapshot["caseId"],
                approvers=" → ".join(person["name"] for person in snapshot["approvers"]))


def render_bytes(template, snapshot):
    document = DocxTemplate(BytesIO(template))
    environment = SandboxedEnvironment(undefined=StrictUndefined, autoescape=True)
    document.render(context(snapshot), jinja_env=environment, autoescape=True)
    output = BytesIO()
    document.save(output)
    if output.tell() > MAX_BYTES:
        raise ValueError("DOCUMENT_TOO_LARGE")
    return output.getvalue()


def execute(job, snapshot):
    client = storage()
    reference = snapshot["template"]
    response = client.get_object(Bucket=BUCKET, Key=reference["key"])
    with response["Body"] as body:
        template = body.read(MAX_BYTES + 1)
    if len(template) > MAX_BYTES or hashlib.sha256(template).hexdigest() != reference["sha256"]:
        raise ValueError("TEMPLATE_CHECKSUM_MISMATCH")
    output = render_bytes(template, snapshot)
    key = f'tenants/{job["tenant_id"]}/documents/{job["job_id"]}/attempt-{job["attempt"]}/fence-{job["fence"]}/{uuid4()}.docx'
    client.put_object(Bucket=BUCKET, Key=key, Body=output, IfNoneMatch="*",
                      ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    return dict(key=key, sha256=hashlib.sha256(output).hexdigest(), size=len(output))
