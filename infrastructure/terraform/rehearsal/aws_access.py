"""One-time, user-run IAM bootstrap. Default is read-only; --apply grants access.

Run in the account owner's AWS CloudShell after reviewing ACCESS.md. This file
does not create workloads, change the account plan, or generate access keys.
It requires only Python 3 and AWS CLI, both available in standard CloudShell.
"""

import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import unquote

REGION = "us-east-1"
USER = "caseflow-operator"
PROJECT = "caseflow-rehearsal"
BOUNDARY = "caseflow-access-runtime-boundary"
INFRA = "caseflow-access-infrastructure"
IDENTITY = "caseflow-access-identity-storage"


def statement(sid, actions, resources, condition=None, effect="Allow"):
    result = {"Sid": sid, "Effect": effect, "Action": actions, "Resource": resources}
    if condition:
        result["Condition"] = condition
    return result


def policies(account):
    if not re.fullmatch(r"[0-9]{12}", account):
        raise ValueError("Expected a 12-digit AWS account identifier")
    regional = {"StringEquals": {"aws:RequestedRegion": REGION}}
    arn = lambda service, resource: f"arn:aws:{service}:{REGION}:{account}:{resource}"
    bucket = f"arn:aws:s3:::{PROJECT}-{account}-{REGION}"
    state = f"arn:aws:s3:::{PROJECT}-state-{account}-{REGION}"
    roles = [
        f"arn:aws:iam::{account}:role/{PROJECT}-{suffix}"
        for suffix in ("execution", "api", "worker", "bootstrap", "auxiliary")
    ]
    boundary_arn = f"arn:aws:iam::{account}:policy/{BOUNDARY}"
    secrets = [arn("secretsmanager", f"secret:{PROJECT}/*")]
    logs = [
        arn("logs", f"log-group:/caseflow/{PROJECT}"),
        arn("logs", f"log-group:/caseflow/{PROJECT}:*"),
    ]
    repositories = [arn("ecr", f"repository/{PROJECT}/*")]

    runtime = [
        statement(
            "SecretsManagerEncryption",
            ["kms:Decrypt", "kms:GenerateDataKey"],
            [arn("kms", "key/*")],
            {
                "StringEquals": {
                    "kms:ViaService": f"secretsmanager.{REGION}.amazonaws.com",
                    "kms:CallerAccount": account,
                },
                "ForAnyValue:StringEquals": {
                    "kms:ResourceAliases": ["alias/aws/secretsmanager"]
                },
            },
        ),
        statement(
            "Objects",
            ["s3:GetObject", "s3:GetObjectVersion", "s3:PutObject", "s3:DeleteObject"],
            [bucket + "/tenants/*"],
        ),
        statement(
            "ListDocuments",
            ["s3:ListBucket"],
            [bucket],
            {"StringLike": {"s3:prefix": ["tenants/*/documents/*"]}},
        ),
        statement(
            "RuntimeSecrets",
            ["secretsmanager:GetSecretValue", "secretsmanager:PutSecretValue"],
            secrets,
            regional,
        ),
        statement(
            "RdsBootstrapSecret",
            ["secretsmanager:GetSecretValue"],
            [arn("secretsmanager", "secret:rds!db-*")],
            regional,
        ),
        statement("EcrToken", ["ecr:GetAuthorizationToken"], ["*"], regional),
        statement(
            "PullImages",
            [
                "ecr:BatchCheckLayerAvailability",
                "ecr:GetDownloadUrlForLayer",
                "ecr:BatchGetImage",
            ],
            repositories,
            regional,
        ),
        statement(
            "RuntimeLogs", ["logs:CreateLogStream", "logs:PutLogEvents"], logs, regional
        ),
        statement(
            "ManagedNode",
            [
                "ssm:DescribeAssociation",
                "ssm:GetDeployablePatchSnapshotForInstance",
                "ssm:GetDocument",
                "ssm:DescribeDocument",
                "ssm:GetManifest",
                "ssm:GetParameter",
                "ssm:GetParameters",
                "ssm:ListAssociations",
                "ssm:ListInstanceAssociations",
                "ssm:PutInventory",
                "ssm:PutComplianceItems",
                "ssm:PutConfigurePackageResult",
                "ssm:UpdateAssociationStatus",
                "ssm:UpdateInstanceAssociationStatus",
                "ssm:UpdateInstanceInformation",
                "ssmmessages:CreateControlChannel",
                "ssmmessages:CreateDataChannel",
                "ssmmessages:OpenControlChannel",
                "ssmmessages:OpenDataChannel",
                "ec2messages:AcknowledgeMessage",
                "ec2messages:DeleteMessage",
                "ec2messages:FailMessage",
                "ec2messages:GetEndpoint",
                "ec2messages:GetMessages",
                "ec2messages:SendReply",
            ],
            ["*"],
            regional,
        ),
    ]

    infrastructure = [
        statement(
            "NetworkAndDisk",
            [
                "ec2:CreateVpc",
                "ec2:DeleteVpc",
                "ec2:ModifyVpcAttribute",
                "ec2:CreateSubnet",
                "ec2:DeleteSubnet",
                "ec2:ModifySubnetAttribute",
                "ec2:CreateInternetGateway",
                "ec2:DeleteInternetGateway",
                "ec2:AttachInternetGateway",
                "ec2:DetachInternetGateway",
                "ec2:CreateRouteTable",
                "ec2:DeleteRouteTable",
                "ec2:CreateRoute",
                "ec2:ReplaceRoute",
                "ec2:DeleteRoute",
                "ec2:AssociateRouteTable",
                "ec2:DisassociateRouteTable",
                "ec2:ReplaceRouteTableAssociation",
                "ec2:CreateSecurityGroup",
                "ec2:DeleteSecurityGroup",
                "ec2:AuthorizeSecurityGroupIngress",
                "ec2:AuthorizeSecurityGroupEgress",
                "ec2:RevokeSecurityGroupIngress",
                "ec2:RevokeSecurityGroupEgress",
                "ec2:ModifySecurityGroupRules",
                "ec2:UpdateSecurityGroupRuleDescriptionsIngress",
                "ec2:UpdateSecurityGroupRuleDescriptionsEgress",
                "ec2:CreateVolume",
                "ec2:DeleteVolume",
                "ec2:AttachVolume",
                "ec2:DetachVolume",
                "ec2:ModifyVolume",
                "ec2:CreateTags",
                "ec2:DeleteTags",
                "ec2:TerminateInstances",
                "ec2:StopInstances",
                "ec2:StartInstances",
                "ec2:ModifyInstanceAttribute",
                "ec2:ModifyInstanceMetadataOptions",
            ],
            ["*"],
            regional,
        ),
        statement(
            "LaunchReviewedInstanceSize",
            ["ec2:RunInstances"],
            [arn("ec2", "instance/*")],
            {
                "StringEquals": {
                    "aws:RequestedRegion": REGION,
                    "ec2:InstanceType": "m7i-flex.large",
                }
            },
        ),
        statement(
            "LaunchDependencies",
            ["ec2:RunInstances"],
            [
                f"arn:aws:ec2:{REGION}::image/ami-*",
                arn("ec2", "subnet/*"),
                arn("ec2", "security-group/*"),
                arn("ec2", "network-interface/*"),
                arn("ec2", "volume/*"),
            ],
            regional,
        ),
        statement(
            "ApplicationContainers",
            [
                "ecs:CreateCluster",
                "ecs:DeleteCluster",
                "ecs:UpdateCluster",
                "ecs:CreateService",
                "ecs:UpdateService",
                "ecs:DeleteService",
                "ecs:TagResource",
                "ecs:UntagResource",
                "ecs:RunTask",
                "ecs:StopTask",
                "ecs:DeregisterTaskDefinition",
            ],
            [
                arn("ecs", f"cluster/{PROJECT}"),
                arn("ecs", f"service/{PROJECT}/*"),
                arn("ecs", f"task/{PROJECT}/*"),
                arn("ecs", f"task-definition/{PROJECT}-*:*"),
            ],
            regional,
        ),
        statement(
            "RegisterTaskDefinition", ["ecs:RegisterTaskDefinition"], ["*"], regional
        ),
        statement(
            "Images",
            [
                "ecr:CreateRepository",
                "ecr:DeleteRepository",
                "ecr:TagResource",
                "ecr:UntagResource",
                "ecr:PutImage",
                "ecr:InitiateLayerUpload",
                "ecr:UploadLayerPart",
                "ecr:CompleteLayerUpload",
                "ecr:BatchDeleteImage",
                "ecr:PutImageScanningConfiguration",
                "ecr:PutImageTagMutability",
            ],
            repositories,
            regional,
        ),
        statement("EcrToken", ["ecr:GetAuthorizationToken"], ["*"], regional),
        statement(
            "Database",
            [
                "rds:CreateDBInstance",
                "rds:ModifyDBInstance",
                "rds:DeleteDBInstance",
                "rds:CreateDBSubnetGroup",
                "rds:ModifyDBSubnetGroup",
                "rds:DeleteDBSubnetGroup",
                "rds:CreateDBParameterGroup",
                "rds:ModifyDBParameterGroup",
                "rds:DeleteDBParameterGroup",
                "rds:AddTagsToResource",
                "rds:RemoveTagsFromResource",
                "rds:CreateDBSnapshot",
                "rds:DeleteDBSnapshot",
            ],
            [
                arn("rds", f"db:{PROJECT}"),
                arn("rds", f"subgrp:{PROJECT}"),
                arn("rds", f"pg:{PROJECT}"),
                arn("rds", f"snapshot:{PROJECT}-*"),
            ],
            regional,
        ),
        statement(
            "Edge",
            [
                "elasticloadbalancing:CreateLoadBalancer",
                "elasticloadbalancing:DeleteLoadBalancer",
                "elasticloadbalancing:ModifyLoadBalancerAttributes",
                "elasticloadbalancing:SetSecurityGroups",
                "elasticloadbalancing:SetSubnets",
                "elasticloadbalancing:CreateTargetGroup",
                "elasticloadbalancing:DeleteTargetGroup",
                "elasticloadbalancing:ModifyTargetGroup",
                "elasticloadbalancing:ModifyTargetGroupAttributes",
                "elasticloadbalancing:RegisterTargets",
                "elasticloadbalancing:DeregisterTargets",
                "elasticloadbalancing:CreateListener",
                "elasticloadbalancing:DeleteListener",
                "elasticloadbalancing:ModifyListener",
                "elasticloadbalancing:CreateRule",
                "elasticloadbalancing:ModifyRule",
                "elasticloadbalancing:DeleteRule",
                "elasticloadbalancing:AddTags",
                "elasticloadbalancing:RemoveTags",
            ],
            ["*"],
            regional,
        ),
        statement(
            "Certificates",
            [
                "acm:RequestCertificate",
                "acm:DeleteCertificate",
                "acm:AddTagsToCertificate",
                "acm:RemoveTagsFromCertificate",
            ],
            ["*"],
            regional,
        ),
        statement(
            "Discovery",
            [
                "servicediscovery:CreatePrivateDnsNamespace",
                "servicediscovery:DeleteNamespace",
                "servicediscovery:CreateService",
                "servicediscovery:UpdateService",
                "servicediscovery:DeleteService",
                "servicediscovery:TagResource",
                "servicediscovery:UntagResource",
            ],
            ["*"],
            regional,
        ),
        statement(
            "Logs",
            [
                "logs:CreateLogGroup",
                "logs:DeleteLogGroup",
                "logs:PutRetentionPolicy",
                "logs:DeleteRetentionPolicy",
                "logs:TagResource",
                "logs:UntagResource",
                "logs:TagLogGroup",
                "logs:UntagLogGroup",
            ],
            logs,
            regional,
        ),
    ]

    identity_storage = [
        statement(
            "CreateBoundedRoles",
            ["iam:CreateRole", "iam:PutRolePermissionsBoundary"],
            roles,
            {"StringEquals": {"iam:PermissionsBoundary": boundary_arn}},
        ),
        statement(
            "ManageApplicationRoles",
            [
                "iam:DeleteRole",
                "iam:UpdateRole",
                "iam:UpdateAssumeRolePolicy",
                "iam:PutRolePolicy",
                "iam:DeleteRolePolicy",
                "iam:TagRole",
                "iam:UntagRole",
            ],
            roles,
        ),
        statement(
            "ManagedRuntimePolicies",
            ["iam:AttachRolePolicy", "iam:DetachRolePolicy"],
            roles,
            {
                "ArnEquals": {
                    "iam:PolicyARN": [
                        "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy",
                        "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore",
                    ]
                }
            },
        ),
        statement(
            "PassApplicationRoles",
            ["iam:PassRole"],
            roles,
            {
                "StringEquals": {
                    "iam:PassedToService": [
                        "ecs-tasks.amazonaws.com",
                        "ec2.amazonaws.com",
                    ]
                }
            },
        ),
        statement(
            "InstanceProfile",
            [
                "iam:CreateInstanceProfile",
                "iam:DeleteInstanceProfile",
                "iam:AddRoleToInstanceProfile",
                "iam:RemoveRoleFromInstanceProfile",
                "iam:TagInstanceProfile",
                "iam:UntagInstanceProfile",
            ],
            [f"arn:aws:iam::{account}:instance-profile/{PROJECT}"],
        ),
        statement(
            "AwsServiceRoles",
            ["iam:CreateServiceLinkedRole"],
            [f"arn:aws:iam::{account}:role/aws-service-role/*"],
            {
                "StringEquals": {
                    "iam:AWSServiceName": [
                        "ecs.amazonaws.com",
                        "elasticloadbalancing.amazonaws.com",
                        "rds.amazonaws.com",
                        "servicediscovery.amazonaws.com",
                    ]
                }
            },
        ),
        statement(
            "ProjectBuckets",
            [
                "s3:CreateBucket",
                "s3:DeleteBucket",
                "s3:PutBucketPublicAccessBlock",
                "s3:PutBucketVersioning",
                "s3:PutEncryptionConfiguration",
                "s3:PutBucketPolicy",
                "s3:DeleteBucketPolicy",
                "s3:PutBucketTagging",
                "s3:GetBucketLocation",
                "s3:ListBucket",
                "s3:ListBucketVersions",
            ],
            [bucket, state],
        ),
        statement(
            "ProjectObjectsAndState",
            [
                "s3:GetObject",
                "s3:GetObjectVersion",
                "s3:PutObject",
                "s3:DeleteObject",
                "s3:DeleteObjectVersion",
            ],
            [bucket + "/*", state + "/caseflow/rehearsal/*"],
        ),
        statement(
            "ProjectSecretContainers",
            [
                "secretsmanager:CreateSecret",
                "secretsmanager:DeleteSecret",
                "secretsmanager:RestoreSecret",
                "secretsmanager:TagResource",
                "secretsmanager:UntagResource",
                "secretsmanager:UpdateSecret",
                "secretsmanager:GetSecretValue",
            ],
            secrets,
            regional,
        ),
        statement(
            "RdsManagedSecretCreation",
            ["secretsmanager:CreateSecret", "secretsmanager:TagResource"],
            [arn("secretsmanager", "secret:rds!db-*")],
            regional,
        ),
        statement(
            "DnsSetup",
            [
                "route53:CreateHostedZone",
                "route53:DeleteHostedZone",
                "route53:ChangeTagsForResource",
                "route53:ChangeResourceRecordSets",
                "route53:AssociateVPCWithHostedZone",
                "route53:DisassociateVPCFromHostedZone",
            ],
            ["*"],
        ),
        statement(
            "OperateTaggedHost",
            ["ssm:SendCommand", "ssm:StartSession"],
            [arn("ec2", "instance/*")],
            {
                "StringEquals": {
                    "ssm:resourceTag/Project": "caseflow",
                    "aws:RequestedRegion": REGION,
                }
            },
        ),
        statement(
            "OperationDocuments",
            ["ssm:SendCommand", "ssm:StartSession"],
            [
                f"arn:aws:ssm:{REGION}::document/AWS-RunShellScript",
                f"arn:aws:ssm:{REGION}::document/AWS-StartPortForwardingSession",
                f"arn:aws:ssm:{REGION}::document/AWS-StartPortForwardingSessionToRemoteHost",
            ],
            regional,
        ),
        statement(
            "OperatorSessions",
            ["ssm:TerminateSession", "ssm:ResumeSession"],
            [arn("ssm", "session/${aws:username}-*")],
            regional,
        ),
        statement(
            "NoPaidUpgradeOrOrganizations",
            ["freetier:UpgradeAccountPlan", "organizations:*"],
            ["*"],
            effect="Deny",
        ),
    ]
    documents = {BOUNDARY: runtime, INFRA: infrastructure, IDENTITY: identity_storage}
    return {
        name: {"Version": "2012-10-17", "Statement": entries}
        for name, entries in documents.items()
    }


def aws(*args, missing_ok=False):
    # Large policy documents travel through a local file, not shell interpolation.
    with tempfile.TemporaryDirectory(prefix="caseflow-iam-") as directory:
        arguments = list(args)
        if "--policy-document" in arguments:
            index = arguments.index("--policy-document") + 1
            document = Path(directory) / "policy.json"
            document.write_text(arguments[index], encoding="utf-8")
            arguments[index] = "file://" + document.as_posix()
        result = subprocess.run(
            [
                "aws",
                *arguments,
                "--region",
                REGION,
                "--output",
                "json",
                "--no-cli-pager",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    if result.returncode:
        if missing_ok and "(NoSuchEntity)" in result.stderr:
            return None
        # No credential operations are invoked, and raw diagnostic output is not echoed.
        error = re.search(r"\(([A-Za-z0-9]+)\)", result.stderr)
        raise RuntimeError(
            f"AWS {args[0]} {args[1]} failed: {error.group(1) if error else 'see console permissions'}"
        )
    return json.loads(result.stdout) if result.stdout.strip() else {}


def configure(account, call=aws, apply=False):
    documents = policies(account)
    if call("sts", "get-caller-identity")["Account"] != account:
        raise ValueError("Wrong AWS account; no changes made")
    plan = call("freetier", "get-account-plan-state")
    if plan["accountPlanType"] != "FREE" or plan["accountPlanStatus"] != "ACTIVE":
        raise ValueError("An ACTIVE Free plan is required; no changes made")
    user = call("iam", "get-user", "--user-name", USER)["User"]
    if user["Arn"] != f"arn:aws:iam::{account}:user/{USER}":
        raise ValueError("Unexpected IAM user path; no changes made")
    if user.get("PermissionsBoundary"):
        raise ValueError(
            "Existing operator boundary requires a separate review; no changes made"
        )
    baseline = {
        "arn:aws:iam::aws:policy/" + name
        for name in [
            "ReadOnlyAccess",
            "SignInLocalDevelopmentAccess",
            "IAMUserChangePassword",
        ]
    }
    allowed = baseline | {
        f"arn:aws:iam::{account}:policy/{name}" for name in [INFRA, IDENTITY]
    }
    attached = call("iam", "list-attached-user-policies", "--user-name", USER)[
        "AttachedPolicies"
    ]
    required = {
        "arn:aws:iam::aws:policy/ReadOnlyAccess",
        "arn:aws:iam::aws:policy/SignInLocalDevelopmentAccess",
    }
    if not required.issubset({p["PolicyArn"] for p in attached}):
        raise ValueError(
            "ReadOnlyAccess and SignInLocalDevelopmentAccess are required; no changes made"
        )
    if any(p["PolicyArn"] not in allowed for p in attached):
        raise ValueError(
            "Unexpected existing user policies; review before granting access"
        )
    if call("iam", "list-user-policies", "--user-name", USER)["PolicyNames"]:
        raise ValueError(
            "Unexpected inline user policies; review before granting access"
        )
    if call("iam", "list-groups-for-user", "--user-name", USER)["Groups"]:
        raise ValueError(
            "Unexpected user group permissions; review before granting access"
        )
    boundary_arn = f"arn:aws:iam::{account}:policy/{BOUNDARY}"
    for suffix in ("execution", "api", "worker", "bootstrap", "auxiliary"):
        role_name = PROJECT + "-" + suffix
        role = call("iam", "get-role", "--role-name", role_name, missing_ok=True)
        if (
            role
            and role["Role"]
            .get("PermissionsBoundary", {})
            .get("PermissionsBoundaryArn")
            != boundary_arn
        ):
            raise ValueError(
                f"Existing role is not protected by the expected boundary: {role_name}"
            )
    profile = call(
        "iam",
        "get-instance-profile",
        "--instance-profile-name",
        PROJECT,
        missing_ok=True,
    )
    if profile and any(
        role["Arn"] != f"arn:aws:iam::{account}:role/{PROJECT}-auxiliary"
        for role in profile["InstanceProfile"]["Roles"]
    ):
        raise ValueError(
            "Existing instance profile contains an unrelated role; no changes made"
        )
    missing = []
    for name, document in documents.items():
        if len(json.dumps(document, separators=(",", ":"))) > 6144:
            raise ValueError(f"Policy exceeds AWS size limit: {name}")
        policy_arn = f"arn:aws:iam::{account}:policy/{name}"
        existing = call(
            "iam", "get-policy", "--policy-arn", policy_arn, missing_ok=True
        )
        if existing:
            version = call(
                "iam",
                "get-policy-version",
                "--policy-arn",
                policy_arn,
                "--version-id",
                existing["Policy"]["DefaultVersionId"],
            )["PolicyVersion"]["Document"]
            if isinstance(version, str):
                version = json.loads(unquote(version))
            if version != document:
                raise ValueError(f"Existing policy differs: {name}; no changes made")
        else:
            missing.append(name)
    print("Preflight passed. Three reviewed policies; two attach to caseflow-operator.")
    if not apply:
        print(
            "Preview only: no permissions changed. Use --apply after reviewing ACCESS.md."
        )
        return
    for name in missing:
        call(
            "iam",
            "create-policy",
            "--policy-name",
            name,
            "--policy-document",
            json.dumps(documents[name]),
        )
    attached_arns = {entry["PolicyArn"] for entry in attached}
    for name in [INFRA, IDENTITY]:
        policy_arn = f"arn:aws:iam::{account}:policy/{name}"
        if policy_arn not in attached_arns:
            call(
                "iam",
                "attach-user-policy",
                "--user-name",
                USER,
                "--policy-arn",
                policy_arn,
            )
    print("CaseFlow deployment access configured. No workloads or access keys created.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--render-dir",
        type=Path,
        help="Write policy JSON locally for review; do not call AWS",
    )
    args = parser.parse_args()
    if args.render_dir:
        if args.apply:
            parser.error("--render-dir cannot be combined with --apply")
        args.render_dir.mkdir(parents=True, exist_ok=True)
        for name, document in policies(args.account).items():
            (args.render_dir / (name + ".json")).write_text(
                json.dumps(document, indent=2) + "\n", encoding="utf-8"
            )
        print("Three policy documents rendered for local review. No AWS calls made.")
    else:
        configure(args.account, apply=args.apply)


if __name__ == "__main__":
    main()
