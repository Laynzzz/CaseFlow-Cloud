"""Offline checks for the one-time IAM setup, without granting any permissions."""

import importlib.util
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "aws_access", Path(__file__).with_name("aws_access.py")
)
ACCESS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ACCESS)
ACCOUNT = "123456789012"


def statements(policy):
    return policy["Statement"]


def test_policies_fit_aws_managed_policy_size_and_do_not_grant_administrator():
    policies = ACCESS.policies(ACCOUNT)
    assert len(policies) == 3
    for policy in policies.values():
        assert len(json.dumps(policy, separators=(",", ":"))) <= 6144
        for statement in statements(policy):
            assert "NotAction" not in statement
            assert statement["Action"] != "*"
            assert "*" not in statement["Action"]


def test_role_creation_requires_boundary_and_cannot_edit_it():
    policy = ACCESS.policies(ACCOUNT)["caseflow-access-identity-storage"]
    creation = next(s for s in statements(policy) if s["Sid"] == "CreateBoundedRoles")
    assert creation["Condition"]["StringEquals"]["iam:PermissionsBoundary"] == (
        f"arn:aws:iam::{ACCOUNT}:policy/caseflow-access-runtime-boundary"
    )
    assert len(creation["Resource"]) == 5
    allow_actions = [
        a for s in statements(policy) if s["Effect"] == "Allow" for a in s["Action"]
    ]
    assert not set(allow_actions) & {
        "iam:CreatePolicyVersion",
        "iam:DeleteRolePermissionsBoundary",
        "iam:AttachUserPolicy",
        "iam:PutUserPolicy",
        "iam:CreateAccessKey",
    }
    passed = next(s for s in statements(policy) if s["Sid"] == "PassApplicationRoles")
    assert passed["Resource"] == creation["Resource"]
    assert set(passed["Condition"]["StringEquals"]["iam:PassedToService"]) == {
        "ec2.amazonaws.com",
        "ecs-tasks.amazonaws.com",
    }


def test_runtime_boundary_excludes_iam_and_unrelated_object_storage():
    boundary = ACCESS.policies(ACCOUNT)["caseflow-access-runtime-boundary"]
    for statement in statements(boundary):
        assert not any(action.startswith("iam:") for action in statement["Action"])
        if any(action.startswith("s3:") for action in statement["Action"]):
            assert all("caseflow-rehearsal-" in arn for arn in statement["Resource"])
    assert not any(
        "s3:DeleteObjectVersion" in s["Action"] for s in statements(boundary)
    )


def test_secret_encryption_ceiling_is_limited_to_service_managed_key():
    boundary = ACCESS.policies(ACCOUNT)["caseflow-access-runtime-boundary"]
    kms = [s for s in statements(boundary) if "kms:Decrypt" in s["Action"]]
    assert len(kms) == 1
    assert set(kms[0]["Action"]) == {"kms:Decrypt", "kms:GenerateDataKey"}
    assert kms[0]["Condition"] == {
        "StringEquals": {
            "kms:ViaService": "secretsmanager.us-east-1.amazonaws.com",
            "kms:CallerAccount": ACCOUNT,
        },
        "ForAnyValue:StringEquals": {
            "kms:ResourceAliases": ["alias/aws/secretsmanager"]
        },
    }


class FakeAws:
    def __init__(
        self,
        account=ACCOUNT,
        plan="FREE",
        collision=False,
        unbounded_role=False,
        foreign_profile=False,
        missing_read=False,
    ):
        self.account = account
        self.plan = plan
        self.collision = collision
        self.unbounded_role = unbounded_role
        self.foreign_profile = foreign_profile
        self.missing_read = missing_read
        self.writes = []

    def __call__(self, *args, missing_ok=False):
        service, operation = args[:2]
        if (service, operation) == ("sts", "get-caller-identity"):
            return {"Account": self.account}
        if operation == "get-account-plan-state":
            return {"accountPlanType": self.plan, "accountPlanStatus": "ACTIVE"}
        if operation == "get-user":
            return {"User": {"Arn": f"arn:aws:iam::{ACCOUNT}:user/caseflow-operator"}}
        if operation == "list-attached-user-policies":
            if self.missing_read:
                return {
                    "AttachedPolicies": [
                        {
                            "PolicyArn": "arn:aws:iam::aws:policy/SignInLocalDevelopmentAccess"
                        }
                    ]
                }
            return {
                "AttachedPolicies": [
                    {"PolicyArn": "arn:aws:iam::aws:policy/ReadOnlyAccess"},
                    {
                        "PolicyArn": "arn:aws:iam::aws:policy/SignInLocalDevelopmentAccess"
                    },
                ]
            }
        if operation == "list-user-policies":
            return {"PolicyNames": []}
        if operation == "list-groups-for-user":
            return {"Groups": []}
        if operation == "get-role":
            return {"Role": {"RoleName": args[3]}} if self.unbounded_role else None
        if operation == "get-instance-profile":
            return (
                {
                    "InstanceProfile": {
                        "Roles": [
                            {"Arn": f"arn:aws:iam::{ACCOUNT}:role/unrelated-admin"}
                        ]
                    }
                }
                if self.foreign_profile
                else None
            )
        if operation == "get-policy":
            return {"Policy": {"DefaultVersionId": "v1"}} if self.collision else None
        if operation == "get-policy-version":
            return {
                "PolicyVersion": {
                    "Document": {"Version": "2012-10-17", "Statement": []}
                }
            }
        self.writes.append(args)
        return {}


@pytest.mark.parametrize(
    "fake",
    [
        FakeAws(account="000000000000"),
        FakeAws(plan="PAID"),
        FakeAws(collision=True),
        FakeAws(unbounded_role=True),
        FakeAws(foreign_profile=True),
        FakeAws(missing_read=True),
    ],
)
def test_preflight_failure_never_partially_grants_access(fake):
    with pytest.raises(ValueError):
        ACCESS.configure(ACCOUNT, fake, apply=True)
    assert fake.writes == []


def test_preview_has_no_writes_and_apply_only_creates_policies_and_attaches_two():
    fake = FakeAws()
    ACCESS.configure(ACCOUNT, fake, apply=False)
    assert fake.writes == []
    ACCESS.configure(ACCOUNT, fake, apply=True)
    assert [call[1] for call in fake.writes].count("create-policy") == 3
    assert [call[1] for call in fake.writes].count("attach-user-policy") == 2
    assert all(call[0] == "iam" for call in fake.writes)


def test_account_input_cannot_change_arn_scope():
    with pytest.raises(ValueError):
        ACCESS.policies("123456789012:role/*")


def test_instance_type_condition_only_applies_to_instances_and_state_key_matches_backend():
    documents = ACCESS.policies(ACCOUNT)
    launch = [
        s
        for s in statements(documents["caseflow-access-infrastructure"])
        if "ec2:RunInstances" in s["Action"]
    ]
    assert len(launch) == 2
    for entry in launch:
        if "ec2:InstanceType" in entry["Condition"]["StringEquals"]:
            assert all(":instance/" in resource for resource in entry["Resource"])
        else:
            assert all(":instance/" not in resource for resource in entry["Resource"])
    objects = next(
        s
        for s in statements(documents["caseflow-access-identity-storage"])
        if s["Sid"] == "ProjectObjectsAndState"
    )
    assert (
        f"arn:aws:s3:::caseflow-rehearsal-state-{ACCOUNT}-us-east-1/caseflow/rehearsal/*"
        in objects["Resource"]
    )
