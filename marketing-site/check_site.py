from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent

REQUIRED = {
    "index.html",
    "subscription.html",
    "support.html",
    "privacy.html",
    "terms.html",
    "risk-disclosure.html",
    "security.html",
}

REQUIRED_EXTERNAL_LINKS = {
    "https://app.bxktraderpro.com/application-access",
    "https://app.bxktraderpro.com/login",
    "https://app.bxktraderpro.com/support",
}

FORBIDDEN_PUBLIC_LANGUAGE = {
    "commercial draft",
    "draft for product development",
    "pre-launch legal review",
}


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        values = dict(attrs)
        href = values.get("href")
        if href:
            self.links.append(href)


def internal_target(href: str):
    if href.startswith(("#", "mailto:", "tel:")):
        return None

    parsed = urlparse(href)

    if parsed.scheme or parsed.netloc:
        return None

    path = parsed.path

    if not path or path == "/":
        return ROOT / "index.html"

    if path.startswith("/"):
        path = path[1:]

    if path.endswith("/"):
        path += "index.html"

    if "." not in Path(path).name:
        return None

    return ROOT / path


def main():
    missing = [
        name
        for name in sorted(REQUIRED)
        if not (ROOT / name).exists()
    ]

    if missing:
        raise SystemExit(
            "Missing required marketing files: "
            + ", ".join(missing)
        )

    all_links = set()

    for html_path in sorted(ROOT.glob("*.html")):
        text = html_path.read_text(
            encoding="utf-8"
        )

        lowered = text.lower()

        for phrase in FORBIDDEN_PUBLIC_LANGUAGE:
            if phrase in lowered:
                raise SystemExit(
                    f"{html_path.name}: public page exposes "
                    f"internal review language: {phrase}"
                )

        parser = LinkParser()
        parser.feed(text)

        for href in parser.links:
            all_links.add(href)

            target = internal_target(href)
            if (
                target is not None
                and not target.exists()
            ):
                raise SystemExit(
                    f"{html_path.name}: broken internal link "
                    f"{href} -> {target.name}"
                )

    missing_external = (
        REQUIRED_EXTERNAL_LINKS
        - all_links
    )

    if missing_external:
        raise SystemExit(
            "Required application links missing: "
            + ", ".join(
                sorted(missing_external)
            )
        )

    print(
        "Marketing site check passed: "
        f"{len(list(ROOT.glob('*.html')))} HTML pages validated."
    )


if __name__ == "__main__":
    main()
