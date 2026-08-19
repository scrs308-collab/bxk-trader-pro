def _safe_score(detail):
    if not isinstance(detail, dict):
        return None

    if detail.get("available") is not True:
        return None

    try:
        score = float(
            detail.get("score")
        )
    except (TypeError, ValueError):
        return None

    return max(
        0.0,
        min(100.0, score),
    )


def evaluate_underlying_condor_decision(
    *,
    symbol,
    stability_score_detail,
    candidate_result,
    verified_profile=False,
):
    """
    Universal observation-only condor decision layer.

    Stability determines provisional market permission.

    This function cannot authorize execution.
    """

    normalized = str(
        symbol or ""
    ).strip().upper() or "UNKNOWN"

    stability_score = _safe_score(
        stability_score_detail
    )

    candidate_result = (
        candidate_result
        if isinstance(
            candidate_result,
            dict,
        )
        else {}
    )

    candidate_available = (
        candidate_result.get(
            "available"
        )
        is True
    )

    pricing_ready = (
        candidate_result.get(
            "pricing_ready"
        )
        is True
    )

    # -------------------------------------------------
    # MARKET PERMISSION
    #
    # Matches BXK strategy thresholds:
    #
    # >= 75  APPROVED
    # >= 50  CAUTION
    # <  50  DENIED
    # -------------------------------------------------

    if stability_score is None:
        market_permission = "WAIT"
        strategy_status = "DENIED"

        permission_label = (
            "Stability score unavailable"
        )

        reason_code = (
            "STABILITY_UNAVAILABLE"
        )

    elif stability_score >= 75:
        market_permission = "TRADE"
        strategy_status = "APPROVED"

        permission_label = (
            "Market stability supports "
            "further trade evaluation"
        )

        if not candidate_available:
            reason_code = (
                "CANDIDATE_UNAVAILABLE"
            )

        elif not pricing_ready:
            reason_code = (
                "CANDIDATE_PRICING_UNAVAILABLE"
            )

        elif verified_profile is not True:
            reason_code = (
                "UNVERIFIED_PROFILE_EXECUTION_BLOCKED"
            )

        else:
            reason_code = (
                "EXECUTION_NOT_AUTHORIZED"
            )

    elif stability_score >= 50:
        market_permission = "CAUTION"
        strategy_status = "CAUTION"

        permission_label = (
            "Market stability warrants caution"
        )

        reason_code = (
            "STABILITY_CAUTION"
        )

    else:
        market_permission = "WAIT"
        strategy_status = "DENIED"

        permission_label = (
            "Market stability does not support "
            "iron-condor entry"
        )

        reason_code = (
            "STABILITY_DENIED"
        )

    candidate_quality_pending = (
        market_permission == "TRADE"
        and candidate_available
        and pricing_ready
    )

    return {
        "available": (
            stability_score
            is not None
        ),

        "underlying": normalized,
        "strategy": "IRON CONDOR",

        "verified_profile": (
            verified_profile is True
        ),

        "stability_score": (
            round(
                stability_score,
                1,
            )
            if stability_score is not None
            else None
        ),

        "strategy_status":
            strategy_status,

        "market_permission":
            market_permission,

        "permission_label":
            permission_label,

        "candidate_available":
            candidate_available,

        "candidate_pricing_ready":
            pricing_ready,

        # Candidate quality scoring is a separate
        # future layer.
        "trade_quality_score": None,
        "trade_quality_required": True,

        "candidate_quality_pending":
            candidate_quality_pending,

        # Deliberately fail closed.
        "final_decision": "NO TRADE",

        "signal_ready": False,
        "execution_enabled": False,
        "observation_only": True,

        "reason_code":
            reason_code,
    }
