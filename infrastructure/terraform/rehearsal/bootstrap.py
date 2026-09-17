"""One-off ECS bootstrap. Reads/writes secrets by ARN; prints no credentials."""
import base64
import json
import os
from pathlib import Path
import secrets
import boto3
import psycopg
from psycopg import sql

def main():
    config = json.loads(os.environ["BOOTSTRAP_CONFIG"])
    Path("/tmp/rds-ca.pem").write_bytes(base64.b64decode(config["ca"]))
    store = boto3.client("secretsmanager", region_name=config["region"])


    def value(name):
        arn = config["secrets"][name]
        try:
            return store.get_secret_value(SecretId=arn)["SecretString"]
        except store.exceptions.ResourceNotFoundException:
            password = secrets.token_hex(24)
            store.put_secret_value(SecretId=arn, SecretString=password)
            return password


    master = json.loads(store.get_secret_value(SecretId=config["master"])["SecretString"])
    with psycopg.connect(host=config["database"], dbname="caseflow", user=master["username"],
                         password=master["password"], sslmode="verify-full", sslrootcert="/tmp/rds-ca.pem",
                         autocommit=True, connect_timeout=10) as db:
        for key, role in [("migrator", "caseflow_migrator"), ("api", "caseflow_api"),
                          ("worker", "caseflow_worker"), ("keycloak-db", "caseflow_keycloak")]:
            password = value(key)
            if not db.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (role,)).fetchone():
                db.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(sql.Identifier(role), sql.Literal(password)))
            else:
                # Stored secret is stable on rerun; do not create a new credential allowance.
                db.execute(sql.SQL("ALTER ROLE {} PASSWORD {}").format(sql.Identifier(role), sql.Literal(password)))
        db.execute("REVOKE ALL ON DATABASE caseflow FROM PUBLIC")
        db.execute("GRANT CONNECT ON DATABASE caseflow TO caseflow_migrator,caseflow_api,caseflow_worker")
        db.execute("GRANT CREATE ON DATABASE caseflow TO caseflow_migrator")
        db.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
        db.execute("GRANT USAGE,CREATE ON SCHEMA public TO caseflow_migrator")
        if not db.execute("SELECT 1 FROM pg_database WHERE datname='keycloak'").fetchone():
            db.execute(sql.SQL("GRANT caseflow_keycloak TO {}").format(sql.Identifier(master["username"])))
            db.execute("CREATE DATABASE keycloak OWNER caseflow_keycloak")
        db.execute("REVOKE ALL ON DATABASE keycloak FROM PUBLIC")
        db.execute("GRANT CONNECT ON DATABASE keycloak TO caseflow_keycloak")

    value("keycloak-admin")
    password = value("demo-password")
    realm = {"realm": "caseflow", "enabled": True, "sslRequired": "external", "registrationAllowed": False,
             "clients": [{"clientId": "caseflow-web", "enabled": True, "publicClient": True,
                          "standardFlowEnabled": True, "directAccessGrantsEnabled": False,
                          "redirectUris": [config["app"] + "/*"], "webOrigins": [config["app"]],
                          "attributes": {"pkce.code.challenge.method": "S256", "post.logout.redirect.uris": config["app"] + "/*"},
                          "protocolMappers": [{"name": "api audience", "protocol": "openid-connect", "protocolMapper": "oidc-audience-mapper",
                                               "config": {"included.custom.audience": "caseflow-api", "access.token.claim": "true"}}]}],
             "users": [{"username": name, "enabled": True, "firstName": name, "lastName": "Rehearsal",
                        "email": name + "@caseflow.example", "emailVerified": True,
                        "credentials": [{"type": "password", "value": password, "temporary": False}]}
                       for name in ["requester", "manager", "finance", "admin", "auditor", "outsider"]]}
    store.put_secret_value(SecretId=config["secrets"]["keycloak-realm"], SecretString=json.dumps(realm))
    print("Bootstrap complete: runtime role grants and synthetic realm are stored; no secret values emitted.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("Bootstrap failed: " + type(error).__name__ + "; inspect the bounded configuration and retry. Secret values and driver details are suppressed.")
        raise SystemExit(1) from None
