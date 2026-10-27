"""No application imports, secrets, broker calls or HTTP requests."""
import argparse
import json
import shutil
import socket
import ssl
import sys

def check(probe=False):
    if sys.version_info < (3, 12, 16):
        raise RuntimeError("Patched Python 3.12.16 or later required")
    context = ssl.create_default_context()
    if not context.check_hostname or context.verify_mode != ssl.CERT_REQUIRED:
        raise RuntimeError("TLS verification is not required")
    runtimes = {name: bool(shutil.which(name)) for name in ("node", "php")}
    if any(runtimes.values()):
        raise RuntimeError("Unexpected Node/PHP runtime: assess its trust store before deployment")
    result = {"python": sys.version.split()[0], "openssl": ssl.OPENSSL_VERSION,
              "ca_count": len(context.get_ca_certs()), "runtimes_present": runtimes}
    if probe:
        with socket.create_connection(("pypi.org", 443), timeout=15) as connection:
            with context.wrap_socket(connection, server_hostname="pypi.org"):
                pass
        rejected = {}
        for prefix in ("dv-g3b", "dv-g3b-aaa", "dv-g3b-noct", "dv-g3b-aaa-noct"):
            host = prefix + "-emudhra.we-have-a-problem.com"
            try:
                with socket.create_connection((host, 443), timeout=15) as connection:
                    with context.wrap_socket(connection, server_hostname=host):
                        pass
            except ssl.SSLCertVerificationError as error:
                if error.verify_code not in (20, 21, 23, 27, 28):
                    raise RuntimeError("Inconclusive certificate error: " + str(error.verify_code)) from error
                rejected[host] = error.verify_code
            else:
                raise RuntimeError("Compromised chain accepted: " + host)
        result["incident_chains_rejected"] = rejected
    return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", action="store_true")
    print(json.dumps(check(parser.parse_args().probe), indent=2))
