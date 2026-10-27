"""Offline TLS checks. Never imports the application or contacts a broker."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import socket
import ssl
import sys

import certifi
from cryptography import x509
from cryptography.x509.oid import NameOID


def inspect_trust(compromised_sha256=None):
    version = importlib.metadata.version("certifi")
    if tuple(map(int, version.split("."))) < (2026, 10, 19):
        raise RuntimeError("certifi is older than the required security floor")
    if os.environ.get("PYTHONHTTPSVERIFY") == "0" or os.environ.get("NODE_TLS_REJECT_UNAUTHORIZED") == "0":
        raise RuntimeError("TLS verification has been disabled")
    bundle = x509.load_pem_x509_certificates(Path(certifi.where()).read_bytes())
    if any(attr.value == "emSign ECC Root CA - G3" for certificate in bundle
           for attr in certificate.subject.get_attributes_for_oid(NameOID.COMMON_NAME)):
        raise RuntimeError("Affected emSign ECC Root CA - G3 remains in certifi bundle")
    contexts = {"system": ssl.create_default_context(), "certifi": ssl.create_default_context(cafile=certifi.where())}
    result = {"certifi": version, "openssl": ssl.OPENSSL_VERSION,
              "additional_runtimes_present": {name: bool(shutil.which(name)) for name in ("node", "php")},
              "custom_ca_override_present": any(os.environ.get(name) for name in
                  ("SSL_CERT_FILE", "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE", "NODE_EXTRA_CA_CERTS")),
              "stores": {}}
    fingerprint = None
    if compromised_sha256:
        fingerprint = compromised_sha256.replace(":", "").lower()
        if len(fingerprint) != 64 or any(c not in "0123456789abcdef" for c in fingerprint):
            raise ValueError("Expected a SHA-256 certificate fingerprint")
    for name, context in contexts.items():
        if context.verify_mode != ssl.CERT_REQUIRED or not context.check_hostname:
            raise RuntimeError(f"TLS verification is not required by {name}")
        certificates = context.get_ca_certs(binary_form=True)
        emsign_present = False
        for der in certificates:
            subject = x509.load_der_x509_certificate(der).subject
            if any(attr.value == "emSign ECC Root CA - G3" for attr in subject.get_attributes_for_oid(NameOID.COMMON_NAME)):
                emsign_present = True
        if fingerprint and any(hashlib.sha256(c).hexdigest() == fingerprint for c in certificates):
            raise RuntimeError(f"Compromised certificate remains trusted by {name}")
        result["stores"][name] = {"ca_count": len(certificates), "verification_required": True,
                                  "emsign_g3_present": emsign_present}
    result["certifi_emsign_g3_absence_checked"] = True
    result["additional_fingerprint_checked"] = bool(fingerprint)
    return result


def probe_incident_hosts():
    """Public researcher endpoints only; no HTTP requests, credentials or proxies."""
    hosts = (
        "dv-g3b-emudhra.we-have-a-problem.com",
        "dv-g3b-aaa-emudhra.we-have-a-problem.com",
        "dv-g3b-noct-emudhra.we-have-a-problem.com",
        "dv-g3b-aaa-noct-emudhra.we-have-a-problem.com",
    )
    result = {}
    for name, context in (("system", ssl.create_default_context()),
                          ("certifi", ssl.create_default_context(cafile=certifi.where()))):
        # A failed network is never counted as a successful security check.
        with socket.create_connection(("pypi.org", 443), timeout=15) as connection:
            with context.wrap_socket(connection, server_hostname="pypi.org"):
                pass
        for host in hosts:
            try:
                with socket.create_connection((host, 443), timeout=15) as connection:
                    with context.wrap_socket(connection, server_hostname=host):
                        pass
            except ssl.SSLCertVerificationError as error:
                # Expiry/hostname failures do not prove this incident is mitigated.
                if error.verify_code not in (20, 21, 23, 27, 28):
                    raise RuntimeError(f"{name}/{host}: inconclusive certificate failure {error.verify_code}") from error
                result[f"{name}/{host}"] = {"rejected": True, "verify_code": error.verify_code}
            else:
                raise RuntimeError(f"{name}/{host}: compromised chain accepted")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compromised-sha256")
    parser.add_argument("--probe", action="store_true", help="Probe public incident hosts, with a valid TLS control")
    args = parser.parse_args()
    report = inspect_trust(args.compromised_sha256)
    report["python"] = sys.version.split()[0]
    if args.probe:
        report["incident_probes"] = probe_incident_hosts()
    print(json.dumps(report, indent=2))
