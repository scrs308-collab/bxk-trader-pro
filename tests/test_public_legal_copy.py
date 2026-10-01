from pathlib import Path


def test_public_legal_pages_do_not_show_internal_review_language():
    paths = [
        Path("static/terms.html"),
        Path("static/privacy.html"),
    ]

    forbidden = [
        "commercial draft",
        "pre-launch legal review",
        "draft for product development",
    ]

    for path in paths:
        text = path.read_text(
            encoding="utf-8"
        ).lower()

        for phrase in forbidden:
            assert phrase not in text, (
                f"{path} exposes internal review "
                f"language: {phrase}"
            )
