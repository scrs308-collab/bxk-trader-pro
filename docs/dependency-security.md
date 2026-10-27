# Dependency and certificate safeguards

The incident is GHSA-6q48-6c7w-9gw2. Certifi >=2026.10.19 is the recommended
floor. Python's security announcement also requires patched Python and pip:
https://discuss.python.org/t/information-for-python-users-regarding-emudhra-emsign-ca-certificate-security-incident/109576

Requirements use dependencies.constraints for exact direct and transitive versions.
The initial resolution used Python 3.12 on Windows; Linux Python 3.13.18 CI must
validate installation and the complete existing test suite before rollout.
These are version constraints, not artifact hashes or an installed-runtime SBOM.
The lock establishes a new resolved baseline; it does not claim to reproduce
the unpinned packages installed in earlier Railway deployments.

To refresh deliberately, copy requirements.txt to a temporary input, omit its
`-c dependencies.constraints` line, and run pip-tools 7.6.2 `pip-compile --upgrade
--strip-extras --output-file=dependencies.constraints` against that input.
Review changes, run pip check, audit the complete constraints, then test.
Never let an automatic audit rewrite deployed dependencies.

Railpack is explicitly Python 3.13.18, bootstraps pip 26.2.2 using the wheel and
SHA-256 published by Python's security team, and installs system ca-certificates
in build and runtime images. Rebuild with NO_CACHE=1 for the first rollout.
The pre-deployment trust inspection runs before the existing migration command.
It reports no variable values, credentials, URLs configured in secrets, or account data.

`python scripts/check_tls_trust.py` checks the certifi floor, absence of the
affected root in the certifi PEM bundle, required TLS verification, default
store contents, custom CA override presence, and Node/PHP executables on PATH.
System stores may retain a root while the runtime explicitly blocks affected
intermediates: root presence alone is not proof that a compromised chain is accepted.

`python scripts/check_tls_trust.py --probe` performs TLS handshakes only, using
the researchers' four public DV G3B endpoints (including cross-signed and no-CT
variants), with pypi.org as a valid-certificate control. It tests system and
certifi-configured contexts. DNS, timeout, certificate expiry and hostname errors
do not count as successful rejection. No broker is contacted. This sample does
not cover all eight compromised intermediates or arbitrary custom CA/client paths.
Source: https://emudhra.we-have-a-problem.com/

## Railway inventory inspected on 2026-10-27

| Project | Service | Source branch | Builder/runtime evidence |
| --- | --- | --- | --- |
| prolific-art | bxk-trader-pro | main | Railpack Python |
| prolific-art | bxk-unified-workbench-staging | feature/unified-trade-workbench | Python 3.13.16 build log |
| bxk-unified-workbench-staging | bxk-workbench-staging | feature/unified-trade-workbench | Railpack; separate staging environment |
| prolific-art | bxk-trader-pro-preview | schwab-commercial-readiness | Python 3.13.15 build log |
| prolific-art | bxk-trader-pro-marketing | feature/marketing-site | python:3.12-alpine Dockerfile/build log |
| prolific-art | bxk-marketing-preview | marketing-schwab-readiness | python:3.12-alpine Dockerfile |
| accurate-inspiration | bxk-trader-pro | Not yet inspected | Separate legacy project; verify before rollout |

No Node package manifest, Composer manifest or PHP source was found in the
main source tree; marketing uses browser JavaScript and Python http.server.
That is source/build evidence, not an inspection of binaries inside every running container.
Railway connector has no container execution tool; actual runtime store contents,
Node/PHP executable inventory and custom client stores remain deployment checks.

## Review and rollout

Changes must reach each listed source branch through a reviewed PR. Do not
repoint old services at main; those branches contain different application code.
Run the existing full Linux test workflow and dependency-security workflow.
Marketing PRs must build the Docker image and run its trust probes in the image.
Apply to staging first with live trading false and preview true, fresh build
cache disabled. Verify trust inspection, public incident probes, health and
deployment commit. Then roll out to previews, marketing and finally production.
Retain previous deployment IDs for rollback. Do not merge while checks fail or
while independent review is outstanding. No live trading setting is enabled by
these source changes.
