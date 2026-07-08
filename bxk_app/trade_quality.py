from bxk_app.scanner_settings import scanner_settings


def score_candidate(candidate: dict) -> int:
    score = 100

    credit = candidate.get("credit", 0)
    pop = candidate.get("pop", 0)
    buffer = min(
        candidate.get("put_buffer", 0),
        candidate.get("call_buffer", 0),
    )

    if credit < scanner_settings.minimum_credit:
        score -= 30

    if pop < scanner_settings.minimum_pop:
        score -= 20

    if buffer < 40:
        score -= 15

    wing = candidate.get("wing_width", scanner_settings.wing_width)

    if wing != scanner_settings.wing_width:
        score -= 5

    return max(0, min(score, 100))