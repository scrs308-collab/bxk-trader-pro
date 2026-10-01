import re
from pathlib import Path


TEXT_SUFFIXES = {
    ".py",
    ".js",
    ".html",
    ".css",
    ".md",
    ".toml",
    ".ini",
    ".txt",
    ".example",
    "",
}

SKIP_PARTS = {
    ".git",
    "__pycache__",
    "archive",
}

PATTERNS = {
    "Stripe live key": re.compile(
        r"sk_live_[A-Za-z0-9]{16,}"
    ),
    "Stripe test key": re.compile(
        r"sk_test_[A-Za-z0-9]{16,}"
    ),
    "Stripe webhook secret": re.compile(
        r"whsec_[A-Za-z0-9]{16,}"
    ),
    "PEM private key": re.compile(
        r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
    ),
}


def iter_text_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue

        if any(
            part in SKIP_PARTS
            for part in path.parts
        ):
            continue

        if path.suffix not in TEXT_SUFFIXES:
            continue

        if path.name.endswith(
            (".zip", ".png", ".jpg", ".ico")
        ):
            continue

        yield path


def test_repository_contains_no_common_live_secret_formats():
    findings = []

    root = Path(".")

    for path in iter_text_files(root):
        try:
            text = path.read_text(
                encoding="utf-8"
            )
        except UnicodeDecodeError:
            continue

        for label, pattern in PATTERNS.items():
            if pattern.search(text):
                findings.append(
                    f"{label}: {path}"
                )

    assert findings == [], (
        "Possible committed secrets detected:\n"
        + "\n".join(findings)
    )
