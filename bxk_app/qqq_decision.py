def _safe_score(detail):
    if not isinstance(detail, dict):
        return None

    if detail.get("available") is not True:
        return None

    try:
        score = float(detail.get("score"))
    except (TypeError, ValueError):
        return None

    return max(
        0.0,
        min(100.0, score),
    )


def evaluate_qqq_condor_decision(
    *,
    stability_score_detail,
    candidate_result,
):
    """
    Produce an observation-only QQQ condor decision.

    IMPORTANT:
    Stability permission is NOT a trade-quality score.

    This layer may approve the market environment for
    further consideration, but it cannot authorize an
    order or produce ENTER TRADE.
    """

    stability_score = _safe_score(
        stability_score_detail
    )

    candidate_result = (
        candidate_result
        if isinstance(candidate_result, dict)
        else {}
    )

    candidate_available = (
        candidate_result.get("available")
        is True
    )

    pricing_ready = (
        candidate_result.get("pricing_ready")
        is True
    )

    # -------------------------------------------------
    # PROVISIONAL MARKET PERMISSION
    #
    # Match BXK strategy status thresholds:
    # >= 75 APPROVED
    # >= 50 CAUTION
    # <  50 DENIED
    # -------------------------------------------------

    if stability_score is None:
        market_permission = "WAIT"
        strategy_status = "DENIED"
        permission_label = (
            "QQQ stability score unavailable"
        )
        decision_reason_code = (
            "STABILITY_UNAVAILABLE"
        )

    elif stability_score >= 75:
        market_permission = "TRADE"
        strategy_status = "APPROVED"
        permission_label = (
            "QQQ stability supports further "
            "trade evaluation"
        )

        if not candidate_available:
            decision_reason_code = (
                "CANDIDATE_UNAVAILABLE"
            )

        elif not pricing_ready:
            decision_reason_code = (
                "CANDIDATE_PRICING_UNAVAILABLE"
            )

        else:
            decision_reason_code = (
                "QQQ_EXECUTION_NOT_AUTHORIZED"
            )

    elif stability_score >= 50:
        market_permission = "CAUTION"
        strategy_status = "CAUTION"
        permission_label = (
            "QQQ stability warrants caution"
        )
        decision_reason_code = (
            "STABILITY_CAUTION"
        )

    else:
        market_permission = "WAIT"
        strategy_status = "DENIED"
        permission_label = (
            "QQQ stability does not support "
            "iron-condor entry"
        )
        decision_reason_code = (
            "STABILITY_DENIED"
        )

    candidate_quality_pending = (
        market_permission == "TRADE"
        and candidate_available
        and pricing_ready
    )

    return {
        "available": (
            stability_score is not None
        ),

        "underlying": "QQQ",
        "strategy": "IRON CONDOR",

        "stability_score": (
            round(stability_score, 1)
            if stability_score is not None
            else None
        ),

        "strategy_status": strategy_status,

        "market_permission": (
            market_permission
        ),

        "permission_label": (
            permission_label
        ),

        "candidate_available": (
            candidate_available
        ),

        "candidate_pricing_ready": (
            pricing_ready
        ),

        # We still do not have a QQQ trade-quality score.
        "trade_quality_score": None,
        "trade_quality_required": True,

        "candidate_quality_pending": (
            candidate_quality_pending
        ),

        # Deliberately fail closed.
        "final_decision": "NO TRADE",

        "signal_ready": False,
        "execution_enabled": False,
        "observation_only": True,

        "reason_code": (
            decision_reason_code
        ),
    }
