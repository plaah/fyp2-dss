"""
Financial Impact Estimator Module
===================================
Estimates reimbursement risk for BPJS claims based on INA-CBGs tariff logic.

v2 — Updated for the Surrogate INACBG Grouper architecture:
  - Base tariff is now AUTO-PREDICTED by SurrogateGrouper (not user-supplied)
  - actual_tariff is still user-supplied (what the hospital plans to charge)
  - Risk is driven by MDC confidence + lookup method + tariff gap

Business Rules:
- predicted_base_tariff: SurrogateGrouper output (kelas_3 INA-CBGs rate)
- actual_tariff: what the hospital submitted / plans to charge
- Kelas multipliers (INA-CBGs official):
    kelas_1 = base_tariff × 1.50  (premium ward)
    kelas_2 = base_tariff × 1.25
    kelas_3 = base_tariff × 1.00  (standard BPJS ward)
- Financial risk = gap between actual and BPJS reimbursement ceiling
- Confidence risk: mdc_confidence < 0.60 → prediction uncertain → elevated risk
- Lookup risk: lookup_method == 'none' → CBG unknown → CRITICAL
"""

from __future__ import annotations

from typing import Dict, Any

# ── Domain constants (no magic numbers in business logic) ──────────────────────
KELAS_MULTIPLIERS: Dict[str, float] = {
    "kelas_1": 1.50,
    "kelas_2": 1.25,
    "kelas_3": 1.00,
}

# Tariff ratio thresholds that define risk band boundaries
RISK_THRESHOLDS: Dict[str, float] = {
    "LOW":    1.05,   # submitted ≤ 5% above BPJS ceiling → LOW
    "MEDIUM": 1.20,   # 5–20% above ceiling                → MEDIUM
    "HIGH":   float("inf"),  # > 20% above ceiling          → HIGH
}

# Average days until reimbursement per outcome (based on BPJS processing practice)
CASH_FLOW_DELAY_DAYS: Dict[str, int] = {
    "grouping_valid":    0,   # paid in next BPJS settlement cycle (~14 working days)
    "coding_incomplete": 30,  # requires recode → resubmit → approval cycle
    "grouping_invalid":  90,  # full rework: recode + INACBG re-grouping + resubmit
}

# Reimbursement probability per risk level (Casemix domain estimates)
REIMBURSEMENT_PROB_BY_RISK: Dict[str, float] = {
    "LOW":    0.95,
    "MEDIUM": 0.80,
    "HIGH":   0.60,
}

# Reimbursement probability for non-valid grouping outcomes
REIMBURSEMENT_PROB_SPECIAL: Dict[str, float] = {
    "coding_incomplete": 0.70,  # will be paid after successful recoding
    "grouping_invalid":  0.15,  # requires full rework; high abandonment risk
}

# Default BPJS settlement cycle for valid claims
DEFAULT_SETTLEMENT_DAYS = 14  # working days from submission to payment


class FinancialEstimator:
    """
    Estimates BPJS reimbursement risk for a single claim.

    v2: Accepts SurrogateGrouper output as first argument.
    base_tariff is now AUTO-PREDICTED; actual_tariff is user-supplied.

    Usage:
        estimator = FinancialEstimator()
        result = estimator.estimate(grouper_result, actual_tariff, kelas)
    """

    def estimate(self, grouper_result: Dict[str, Any],
                 actual_tariff: float, kelas: str = "kelas_3") -> Dict[str, Any]:
        """
        Produce a full financial risk assessment for one claim.

        Args:
            grouper_result: Output dict from SurrogateGrouper.predict().
                Must contain: predicted_base_tariff, tariff_by_kelas,
                mdc_confidence, severity_confidence, lookup_method.
            actual_tariff:  What the hospital plans to charge (IDR).
            kelas:          Ward class — "kelas_1" | "kelas_2" | "kelas_3".

        Returns:
            dict with keys:
                reimbursement_amount    (float) — BPJS ceiling for this claim
                submitted_amount        (float) — what hospital submitted
                financial_gap           (float) — submitted minus ceiling (can be negative)
                gap_percentage          (float) — gap as % of ceiling
                risk_level              (str)   — LOW / MEDIUM / HIGH / CRITICAL
                risk_explanation        (str)   — human-readable risk narrative
                estimated_loss_idr      (float) — IDR amount hospital will NOT recover
                cash_flow_risk_days     (int)   — expected delay before reimbursement
                reimbursement_probability (float) — 0.0–1.0 probability of eventual payment
        """
        actual_tariff     = float(actual_tariff or 0)
        kelas             = str(kelas or "kelas_3").strip().lower()
        mdc_confidence    = float(grouper_result.get("mdc_confidence", 1.0))
        lookup_method     = grouper_result.get("lookup_method", "exact")

        # Kelas-adjusted tariff from grouper (already multiplied)
        tariff_by_kelas   = grouper_result.get("tariff_by_kelas", {})
        reimbursement_ceiling = float(
            tariff_by_kelas.get(kelas,
                grouper_result.get("predicted_base_tariff", 0) or 0)
        )

        # Gap = submitted - ceiling; positive = hospital absorbs
        financial_gap = actual_tariff - reimbursement_ceiling
        gap_pct       = round((financial_gap / reimbursement_ceiling * 100), 2) if reimbursement_ceiling > 0 else 0.0
        tariff_ratio  = round(actual_tariff / reimbursement_ceiling, 4) if reimbursement_ceiling > 0 else 1.0

        risk_level    = self._calculate_risk_level_v2(mdc_confidence, lookup_method, tariff_ratio)
        risk_expl     = self._build_risk_explanation_v2(
            risk_level, mdc_confidence, lookup_method, financial_gap, gap_pct,
            grouper_result.get("predicted_cbg_code", "")
        )
        estimated_loss     = max(0.0, financial_gap)
        cash_flow_days     = self._estimate_cash_flow_from_confidence(mdc_confidence, lookup_method)
        reimb_probability  = self._calculate_reimbursement_probability_v2(risk_level)

        return {
            "reimbursement_amount":       round(reimbursement_ceiling, 2),
            "submitted_amount":           round(actual_tariff, 2),
            "financial_gap":              round(financial_gap, 2),
            "gap_percentage":             gap_pct,
            "risk_level":                 risk_level,
            "risk_explanation":           risk_expl,
            "estimated_loss_idr":         round(estimated_loss, 2),
            "cash_flow_risk_days":        cash_flow_days,
            "reimbursement_probability":  reimb_probability,
        }

    # ── v2 Private helpers (surrogate grouper) ────────────────────────────────

    def _calculate_risk_level_v2(self, mdc_confidence: float,
                                  lookup_method: str, tariff_ratio: float) -> str:
        if lookup_method == 'none':
            return "CRITICAL"
        if mdc_confidence < 0.60:
            return "HIGH"
        if tariff_ratio > RISK_THRESHOLDS["MEDIUM"]:
            return "HIGH"
        if tariff_ratio > RISK_THRESHOLDS["LOW"]:
            return "MEDIUM"
        if lookup_method != 'exact':
            return "MEDIUM"   # approximate lookup → slight uncertainty
        return "LOW"

    def _build_risk_explanation_v2(self, risk_level: str, mdc_confidence: float,
                                    lookup_method: str, financial_gap: float,
                                    gap_pct: float, cbg_code: str) -> str:
        if risk_level == "CRITICAL":
            return (
                "CRITICAL: CBG code could not be determined from the given ICD-10 input. "
                "Verify primary diagnosis code and care type before submission."
            )
        confidence_note = ""
        if mdc_confidence < 0.60:
            confidence_note = f" (MDC confidence: {mdc_confidence*100:.0f}% — verify ICD coding)"
        lookup_note = ""
        if lookup_method != 'exact':
            lookup_note = f" CBG lookup used approximate fallback ({lookup_method})."

        if financial_gap > 0:
            gap_msg = (
                f"Submitted amount exceeds INA-CBGs ceiling by {gap_pct:.1f}% "
                f"(IDR {financial_gap:,.0f}). This portion will not be reimbursed."
            )
        elif financial_gap < 0:
            gap_msg = "Submitted amount is within the INA-CBGs reimbursement ceiling."
        else:
            gap_msg = "Submitted amount matches the INA-CBGs ceiling exactly."

        return f"{risk_level}: {gap_msg}{confidence_note}{lookup_note}"

    def _estimate_cash_flow_from_confidence(self, mdc_confidence: float,
                                             lookup_method: str) -> int:
        if lookup_method == 'none':
            return 90
        if mdc_confidence < 0.60:
            return 30
        if lookup_method != 'exact':
            return 14
        return 0

    def _calculate_reimbursement_probability_v2(self, risk_level: str) -> float:
        mapping = {"LOW": 0.95, "MEDIUM": 0.80, "HIGH": 0.60, "CRITICAL": 0.10}
        return mapping.get(risk_level, 0.80)

    # ── Legacy private helpers (kept for backward compatibility) ──────────────

    def _calculate_reimbursement_ceiling(self, base_tariff: float, kelas: str) -> float:
        """
        Apply the INA-CBGs kelas multiplier to base_tariff to get the BPJS
        reimbursement ceiling for this claim.

        Args:
            base_tariff: Official INA-CBGs base rate (IDR) for the CBG code.
            kelas: Ward class — "kelas_1", "kelas_2", or "kelas_3".

        Returns:
            float: Maximum amount BPJS will reimburse for this claim.
        """
        multiplier = KELAS_MULTIPLIERS.get(kelas, KELAS_MULTIPLIERS["kelas_3"])
        return base_tariff * multiplier

    def _calculate_risk_level(self, grouping_outcome: str, tariff_ratio: float) -> str:
        """
        Classify the financial risk level based on grouping outcome and tariff ratio.

        Risk ladder:
          CRITICAL → grouping_invalid (zero reimbursement — full revenue loss)
          HIGH     → coding_incomplete (cash flow blocked) OR ratio > 1.20
          MEDIUM   → grouping_valid AND 1.05 < ratio ≤ 1.20
          LOW      → grouping_valid AND ratio ≤ 1.05

        Args:
            grouping_outcome: "grouping_valid" | "coding_incomplete" | "grouping_invalid"
            tariff_ratio:     actual_tariff / reimbursement_ceiling

        Returns:
            str: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
        """
        if grouping_outcome == "grouping_invalid":
            return "CRITICAL"
        if grouping_outcome == "coding_incomplete":
            return "HIGH"
        # grouping_valid — classify by tariff ratio
        if tariff_ratio <= RISK_THRESHOLDS["LOW"]:
            return "LOW"
        if tariff_ratio <= RISK_THRESHOLDS["MEDIUM"]:
            return "MEDIUM"
        return "HIGH"

    def _build_risk_explanation(
        self, grouping_outcome: str, risk_level: str,
        financial_gap: float, gap_pct: float
    ) -> str:
        """
        Generate a human-readable explanation of the risk assessment.

        Args:
            grouping_outcome: Predicted grouping outcome.
            risk_level:       Classified risk band.
            financial_gap:    IDR gap (submitted − ceiling).
            gap_pct:          Gap as percentage of reimbursement ceiling.

        Returns:
            str: Narrative suitable for display in the DSS UI.
        """
        if grouping_outcome == "grouping_invalid":
            return (
                "CRITICAL: INACBG grouping failed. Full tariff of "
                f"IDR {abs(financial_gap + abs(financial_gap)):,.0f} "
                "is at risk. Recoding required before any reimbursement."
            )
        if grouping_outcome == "coding_incomplete":
            return (
                "HIGH: iDRG coding is incomplete. Claim cannot be submitted to BPJS. "
                f"Expected delay: {CASH_FLOW_DELAY_DAYS['coding_incomplete']} days "
                "until reimbursement after recoding."
            )
        # grouping_valid
        if risk_level == "LOW":
            if financial_gap <= 0:
                return "LOW: Submitted amount is within the INA-CBGs reimbursement ceiling. Full reimbursement expected."
            return f"LOW: Submitted amount exceeds INA-CBGs ceiling by {gap_pct:.1f}% (IDR {financial_gap:,.0f}). Minor excess."
        if risk_level == "MEDIUM":
            return (
                f"MEDIUM: Submitted amount exceeds INA-CBGs ceiling by {gap_pct:.1f}% "
                f"(IDR {financial_gap:,.0f}). This portion will not be reimbursed by BPJS."
            )
        # HIGH for grouping_valid
        return (
            f"HIGH: Submitted amount exceeds INA-CBGs ceiling by {gap_pct:.1f}% "
            f"(IDR {financial_gap:,.0f}). Significant financial loss. "
            "Consider tariff review before submission."
        )

    def _estimate_cash_flow_risk(self, grouping_outcome: str) -> int:
        """
        Return the expected number of additional days before reimbursement
        is received, beyond the standard 14-working-day BPJS settlement cycle.

        Args:
            grouping_outcome: "grouping_valid" | "coding_incomplete" | "grouping_invalid"

        Returns:
            int: Additional delay days (0 = no extra delay beyond normal cycle).
        """
        return CASH_FLOW_DELAY_DAYS.get(grouping_outcome, 0)

    def _calculate_reimbursement_probability(self, grouping_outcome: str, risk_level: str) -> float:
        """
        Estimate the probability that this claim will eventually be reimbursed
        by BPJS, accounting for both grouping outcome and tariff risk level.

        Probabilities are calibrated to observed Casemix coding outcomes at
        Indonesian hospitals (domain expert estimates).

        Args:
            grouping_outcome: Predicted grouping outcome.
            risk_level:       Classified risk band (LOW/MEDIUM/HIGH/CRITICAL).

        Returns:
            float: Probability in [0, 1].
        """
        if grouping_outcome in REIMBURSEMENT_PROB_SPECIAL:
            return REIMBURSEMENT_PROB_SPECIAL[grouping_outcome]
        # grouping_valid — probability depends on tariff risk level
        return REIMBURSEMENT_PROB_BY_RISK.get(risk_level, 0.80)
