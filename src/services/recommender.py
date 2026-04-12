"""
Recommendation Synthesis Module
=================================
Generates actionable recommendations for Casemix coders based on three inputs:

  1. ML prediction outcome  (grouping_valid / coding_incomplete / grouping_invalid)
  2. SHAP feature explanations  (which features drove the prediction)
  3. Financial impact assessment  (risk level + estimated loss)

Recommendations follow Casemix coding best practice for BPJS / INA-CBGs
as practised in Indonesian hospitals.  Each recommendation contains a ranked
action, clinical rationale, and estimated financial impact so the coder can
prioritise their workload effectively.

This module is called by /api/v1/recommend and /api/v1/full-assessment.
"""

from __future__ import annotations

from typing import Dict, List, Any, Optional

# ── Domain constants ───────────────────────────────────────────────────────────

# Days until BPJS settlement under normal circumstances (valid claim)
STANDARD_SETTLEMENT_DAYS = 14  # working days

# Resolution time estimates by outcome
RESOLUTION_DAYS: Dict[str, int] = {
    "grouping_valid":    STANDARD_SETTLEMENT_DAYS,
    "coding_incomplete": 30 + STANDARD_SETTLEMENT_DAYS,   # recode cycle + settlement
    "grouping_invalid":  90 + STANDARD_SETTLEMENT_DAYS,   # full rework + settlement
}

# Maps SHAP feature name → human-readable Casemix coding instruction
FEATURE_ACTION_MAP: Dict[str, str] = {
    "final_success":           "Verify iDRG finalization status before proceeding — final_success flag is False",
    "inacbg_primary_icd10":   "Check ICD-10 code validity in INA-CBGs grouper — code may not be in 2010 ICD-10 version",
    "claim_stage":             "Advance claim to 'final-claim' stage in the Casemix system before submission",
    "idrg_grouping_success":  "Complete iDRG grouping step first — iDRG must succeed before INACBG submission",
    "inacbg_grouping_success": "Verify INACBG grouper result — resubmit through INACBG grouper after ICD correction",
    "idrg_primary_icd10":     "Review primary ICD-10 diagnosis code in iDRG — ensure it matches clinical notes",
    "idrg_icd10_valid":       "ICD-10 code flagged invalid by iDRG — check against ICD-10 2010 reference list",
    "inacbg_icd10_validity":  "INACBG ICD-10 validity flag is 0 — correct diagnosis code and re-run grouper",
    "tariff_ratio":            "Submitted tariff significantly exceeds INA-CBGs ceiling — review tariff before submission",
    "icd_match":               "iDRG and INACBG primary ICD-10 codes differ — ensure consistency across both groupers",
    "entry_type":              "Verify patient entry type (outpatient/inpatient) matches clinical record",
    "mdc_number":              "MDC assignment may be incorrect — re-check primary diagnosis for correct MDC mapping",
}

# ICD-10 prefix → coding tip for common DRG pitfalls
ICD10_CODING_TIPS: Dict[str, str] = {
    "Z09": "Follow-up codes (Z09.x) require the primary condition coded in secondary ICD position",
    "I10": "Hypertension (I10): ensure complications are coded if present (I11–I13) for correct DRG grouping",
    "J18": "Pneumonia (J18.x): specify organism if known (J13–J16) for higher-tariff DRG assignment",
    "N40": "BPH: N40.0 (without LUTS) vs N40.1 (with LUTS) — distinction affects INA-CBGs grouping",
    "E11": "Diabetes mellitus type 2 (E11.x): specify complications (E11.2–E11.8) for correct MDC assignment",
    "I50": "Heart failure (I50.x): specify type (systolic/diastolic/combined) for accurate DRG assignment",
    "K80": "Cholelithiasis (K80.x): procedure code (ICD-9 51.22 laparoscopic cholecystectomy) significantly raises tariff",
    "C":   "Malignant neoplasm: ensure morphology and behaviour coded — affects MDC 4/17 assignment",
    "S":   "Trauma codes (S/T): injury severity and laterality must be specified for correct DRG",
}

# Priority mapping: risk_level → recommendation priority
PRIORITY_MAP: Dict[str, str] = {
    "CRITICAL": "URGENT",
    "HIGH":     "HIGH",
    "MEDIUM":   "MEDIUM",
    "LOW":      "LOW",
}

# Primary action mapping: (grouping_outcome, risk_level) → primary_action
PRIMARY_ACTION_MAP = {
    ("grouping_valid",    "LOW"):      "SUBMIT",
    ("grouping_valid",    "MEDIUM"):   "SUBMIT",
    ("grouping_valid",    "HIGH"):     "REVIEW",
    ("grouping_valid",    "CRITICAL"): "REVIEW",   # edge: shouldn't occur
    ("coding_incomplete", "HIGH"):     "COMPLETE_CODING",
    ("coding_incomplete", "CRITICAL"): "COMPLETE_CODING",
    ("grouping_invalid",  "CRITICAL"): "RECODE",
}


class RecommendationEngine:
    """
    Synthesises surrogate grouper prediction, financial risk, and SHAP
    explanation into ranked, actionable Casemix coding recommendations.
    """

    def synthesize(
        self,
        grouper_result: Dict[str, Any],
        financial_result: Dict[str, Any],
        explanation: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Produce a unified recommendation object from surrogate grouper output.

        Args:
            grouper_result:  dict from SurrogateGrouper.predict().
            financial_result: dict from FinancialEstimator.estimate().
            explanation:     SHAP list from grouper_result['shap_explanation'] (optional).

        Returns:
            dict with keys:
                primary_action          (str)  — SUBMIT | VERIFY_CODING | REVIEW | URGENT_RECODE
                priority                (str)  — LOW | MEDIUM | HIGH | URGENT
                recommendations         (list) — ranked list of action dicts
                warnings                (list) — financial / compliance warnings
                coding_tips             (list) — ICD-10 coding guidance strings
                estimated_resolution_days (int)
                summary                 (str)  — one-sentence executive summary
        """
        mdc_confidence = float(grouper_result.get("mdc_confidence", 1.0))
        lookup_method  = grouper_result.get("lookup_method", "exact")
        cbg_code       = grouper_result.get("predicted_cbg_code", "")
        mdc_letter     = grouper_result.get("predicted_mdc", "")
        risk_level     = financial_result.get("risk_level", "LOW")
        financial_gap  = float(financial_result.get("financial_gap", 0))
        shap_exp       = explanation or grouper_result.get("shap_explanation", [])

        # Determine primary action and priority
        if lookup_method == 'none':
            primary_action = "URGENT_RECODE"
            priority       = "URGENT"
        elif mdc_confidence < 0.60:
            primary_action = "VERIFY_CODING"
            priority       = "HIGH"
        elif risk_level in ("CRITICAL", "HIGH"):
            primary_action = "REVIEW"
            priority       = PRIORITY_MAP.get(risk_level, "HIGH")
        elif financial_gap > 0:
            primary_action = "REVIEW"
            priority       = PRIORITY_MAP.get(risk_level, "MEDIUM")
        else:
            primary_action = "SUBMIT"
            priority       = "LOW"

        recs        = self._build_recommendations_surrogate(
            grouper_result, financial_result, shap_exp
        )
        warnings    = self._build_warnings(financial_result)
        icd10_code  = str(grouper_result.get("predicted_cbg_code", ""))
        coding_tips = self._generate_coding_tips_from_mdc(mdc_letter, cbg_code)
        resolution  = self._estimate_resolution(mdc_confidence, lookup_method)
        summary     = self._build_summary_surrogate(
            cbg_code, mdc_confidence, lookup_method, financial_gap, risk_level
        )

        return {
            "primary_action":            primary_action,
            "priority":                  priority,
            "recommendations":           recs,
            "warnings":                  warnings,
            "coding_tips":               coding_tips,
            "estimated_resolution_days": resolution,
            "summary":                   summary,
        }

    # ── Surrogate grouper recommendation builders ─────────────────────────────

    def _build_recommendations_surrogate(
        self,
        grouper_result: Dict[str, Any],
        financial: Dict[str, Any],
        shap_exp: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        recs = []
        mdc_conf     = float(grouper_result.get("mdc_confidence", 1.0))
        sev_conf     = float(grouper_result.get("severity_confidence", 1.0))
        lookup_method = grouper_result.get("lookup_method", "exact")
        cbg_code     = grouper_result.get("predicted_cbg_code", "")
        cbg_desc     = grouper_result.get("predicted_cbg_description", "")
        financial_gap = float(financial.get("financial_gap", 0))
        risk_level   = financial.get("risk_level", "LOW")
        reimb_amt    = financial.get("reimbursement_amount", 0)

        # Rank 1: CBG prediction result or urgency action
        if lookup_method == 'none':
            recs.append({
                "rank": 1,
                "action": "Kode ICD-10 tidak ditemukan dalam lookup CBG",
                "reason": "Kombinasi kode diagnosis, jenis pelayanan, dan kelas tidak dikenali sistem",
                "impact": "CBG code tidak dapat diprediksi — klaim tidak dapat diproses",
                "confidence": round(mdc_conf, 3),
            })
        else:
            method_label = "Exact Match ✓" if lookup_method == "exact" else f"Fallback ({lookup_method})"
            recs.append({
                "rank": 1,
                "action": f"Prediksi CBG: {cbg_code}",
                "reason": f"{cbg_desc} | Lookup: {method_label}",
                "impact": f"Tarif dasar BPJS: IDR {reimb_amt:,.0f}",
                "confidence": round(mdc_conf, 3),
            })

        # Rank 2: Confidence warning if low
        if mdc_conf < 0.60:
            recs.append({
                "rank": 2,
                "action": "Verifikasi kode ICD-10 diagnosis utama",
                "reason": f"Kepercayaan prediksi MDC rendah ({mdc_conf*100:.0f}%) — kode mungkin tidak spesifik",
                "impact": "Grouping MDC tidak pasti — verifikasi sebelum submit ke INACBG",
                "confidence": round(mdc_conf, 3),
            })
        elif mdc_conf < 0.80:
            recs.append({
                "rank": 2,
                "action": "Konfirmasi spesifisitas kode ICD-10",
                "reason": f"Kepercayaan prediksi MDC sedang ({mdc_conf*100:.0f}%) — pertimbangkan kode yang lebih spesifik",
                "impact": "Kode yang lebih spesifik meningkatkan akurasi prediksi CBG",
                "confidence": round(mdc_conf, 3),
            })

        # Rank 3: Financial gap action
        if financial_gap > 0:
            recs.append({
                "rank": len(recs) + 1,
                "action": f"Tinjau tarif yang akan diajukan",
                "reason": (
                    f"Tarif yang diajukan melebihi ceiling INA-CBGs sebesar "
                    f"IDR {financial_gap:,.0f} ({financial.get('gap_percentage', 0):.1f}%)"
                ),
                "impact": f"IDR {financial_gap:,.0f} tidak akan diganti oleh BPJS",
                "confidence": 1.0,
            })

        # Rank 4: SHAP top feature action
        if shap_exp:
            top_feat = shap_exp[0]
            feat_name = top_feat.get("feature", "")
            feat_action = FEATURE_ACTION_MAP.get(feat_name, f"Perhatikan fitur: {feat_name}")
            recs.append({
                "rank": len(recs) + 1,
                "action": feat_action,
                "reason": f"Faktor terpenting dalam prediksi MDC (impact={top_feat.get('impact', 0):.3f})",
                "impact": "Memperbaiki faktor ini meningkatkan akurasi prediksi",
                "confidence": round(mdc_conf, 3),
            })

        # Rank 5: Severity note
        if sev_conf < 0.80:
            sev_label = grouper_result.get("predicted_severity_label", "")
            recs.append({
                "rank": len(recs) + 1,
                "action": "Konfirmasi tingkat keparahan kasus",
                "reason": f"Prediksi severity '{sev_label}' dengan kepercayaan {sev_conf*100:.0f}%",
                "impact": "Severity menentukan suffix CBG code (0/I/II/III) dan tarif akhir",
                "confidence": round(sev_conf, 3),
            })

        return recs

    def _generate_coding_tips_from_mdc(self, mdc_letter: str, cbg_code: str) -> List[str]:
        tips = []
        mdc_tips = {
            'I': "MDC I (Sirkulasi): Kode komplikasi hipertensi (I11-I13) jika ada — meningkatkan tarif DRG",
            'J': "MDC J (Pernapasan): Spesifikasi organisme pneumonia (J13-J16) jika diketahui",
            'K': "MDC K (Pencernaan): Kode prosedur ICD-9 untuk tindakan bedah — berpengaruh besar pada tarif",
            'N': "MDC N (Genitourinari): Bedakan N40.0 (tanpa LUTS) dan N40.1 (dengan LUTS)",
            'E': "MDC E (Endokrin): Kode komplikasi diabetes (E11.2-E11.8) untuk MDC yang tepat",
            'M': "MDC M (Muskuloskeletal): Kode lateralitas dan tingkat keparahan cedera",
            'O': "MDC O (Obstetri): Kode komplikasi persalinan jika ada — pengaruh besar pada CBG",
            'Q': "MDC Q: Kode ini umumnya untuk kunjungan rawat jalan — verifikasi jenis pelayanan",
            'Z': "MDC Z (Administratif): Kode Z sering ditolak sebagai diagnosis utama BPJS — gunakan diagnosis klinis",
        }
        if mdc_letter in mdc_tips:
            tips.append(mdc_tips[mdc_letter])
        if cbg_code and '?' not in cbg_code:
            tips.append(f"CBG code {cbg_code} terdeteksi — konfirmasi dengan menjalankan INACBG grouper resmi")
        tips.append("Pastikan kode ICD-10 menggunakan versi 2010 (WHO) yang digunakan BPJS Indonesia")
        return tips

    def _estimate_resolution(self, mdc_confidence: float, lookup_method: str) -> int:
        if lookup_method == 'none':
            return 90
        if mdc_confidence < 0.60:
            return 30
        if lookup_method != 'exact':
            return 14
        return STANDARD_SETTLEMENT_DAYS

    def _build_summary_surrogate(self, cbg_code: str, mdc_confidence: float,
                                  lookup_method: str, financial_gap: float,
                                  risk_level: str) -> str:
        if lookup_method == 'none':
            return "CBG code tidak dapat diprediksi — verifikasi kode ICD-10 sebelum submit."
        if mdc_confidence < 0.60:
            return (
                f"Prediksi CBG {cbg_code} dengan kepercayaan rendah ({mdc_confidence*100:.0f}%) — "
                "verifikasi spesifisitas kode diagnosis."
            )
        if financial_gap > 0:
            return (
                f"Prediksi CBG {cbg_code} (risiko {risk_level}) — "
                f"tarif melebihi ceiling BPJS IDR {financial_gap:,.0f}."
            )
        return f"Prediksi CBG: {cbg_code} — siap untuk review Casemix sebelum submit ke INACBG."

    # ── Legacy outcome-specific recommendation builders ───────────────────────

    def _build_recommendations_for_valid(
        self,
        prediction: Dict[str, Any],
        financial: Dict[str, Any],
        explanation: List[Dict[str, Any]],  # noqa: ARG002 — reserved for future SHAP-driven tips
    ) -> List[Dict[str, Any]]:
        """
        Build ranked recommendations when grouping_valid is predicted.

        Args:
            prediction:  prediction_result dict.
            financial:   financial_result dict.
            explanation: SHAP feature list (reserved for future per-feature tips).

        Returns:
            list of recommendation dicts ranked by priority.
        """
        risk_level      = financial.get("risk_level", "LOW")
        reimbursement   = financial.get("reimbursement_amount", 0)
        gap             = financial.get("financial_gap", 0)
        pred_confidence = prediction.get("confidence", {}).get("grouping_valid", 0)
        cbg_code        = financial.get("cbg_code", "")

        recs = []

        if risk_level == "LOW":
            recs.append({
                "rank":       1,
                "action":     "Submit claim to BPJS",
                "reason":     f"Grouping validated. INACBG{(' CBG ' + cbg_code) if cbg_code else ''} accepted. "
                               "No coding issues detected.",
                "impact":     f"IDR {reimbursement:,.0f} reimbursement expected within "
                               f"{STANDARD_SETTLEMENT_DAYS} working days",
                "confidence": round(pred_confidence, 4),
            })
        elif risk_level == "MEDIUM":
            recs.append({
                "rank":       1,
                "action":     "Submit claim to BPJS (with financial note)",
                "reason":     f"Grouping validated. Submitted amount exceeds INA-CBGs ceiling by "
                               f"IDR {gap:,.0f} ({financial.get('gap_percentage', 0):.1f}%).",
                "impact":     f"BPJS will reimburse IDR {reimbursement:,.0f}. "
                               f"Hospital absorbs IDR {gap:,.0f} excess.",
                "confidence": round(pred_confidence, 4),
            })
            recs.append({
                "rank":       2,
                "action":     "Notify finance team of tariff gap",
                "reason":     "Submitted amount exceeds INA-CBGs ceiling — gap will not be reimbursed.",
                "impact":     f"IDR {gap:,.0f} revenue gap documented for internal accounting",
                "confidence": 1.0,
            })
        else:  # HIGH
            recs.append({
                "rank":       1,
                "action":     "Review tariff before submission",
                "reason":     f"Submitted amount exceeds INA-CBGs ceiling by "
                               f"IDR {gap:,.0f} ({financial.get('gap_percentage', 0):.1f}%). "
                               "High financial loss risk.",
                "impact":     f"Potential revenue loss of IDR {gap:,.0f} if submitted as-is",
                "confidence": round(pred_confidence, 4),
            })
            recs.append({
                "rank":       2,
                "action":     "Verify CBG code and kelas assignment",
                "reason":     "Large tariff gap may indicate incorrect kelas or CBG code assignment.",
                "impact":     "Correcting kelas/CBG could reduce financial loss",
                "confidence": 0.75,
            })

        return recs

    def _build_recommendations_for_incomplete(
        self,
        prediction: Dict[str, Any],
        financial: Dict[str, Any],
        explanation: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Build recommendations when coding_incomplete is predicted.
        Maps the top SHAP feature to a specific Casemix coding action.

        Args:
            prediction:  prediction_result dict.
            financial:   financial_result dict.
            explanation: SHAP feature list (first entry is most important).

        Returns:
            list of recommendation dicts.
        """
        top_feature = explanation[0].get("feature") if explanation else None
        delay_days  = financial.get("cash_flow_risk_days", 30)
        pred_conf   = prediction.get("confidence", {}).get("coding_incomplete", 0)

        recs = []

        # Primary action driven by top SHAP feature
        if top_feature and top_feature in FEATURE_ACTION_MAP:
            action_detail = FEATURE_ACTION_MAP[top_feature]
        else:
            action_detail = "Verify all required iDRG fields are complete and finalized"

        recs.append({
            "rank":       1,
            "action":     "Complete iDRG coding before submission",
            "reason":     action_detail,
            "impact":     f"Claim delayed approximately {delay_days} days until recoding is complete",
            "confidence": round(pred_conf, 4),
        })

        recs.append({
            "rank":       2,
            "action":     "Verify iDRG primary ICD-10 code validity",
            "reason":     "iDRG coding must be finalized and ICD-10 validated before INACBG grouping can succeed.",
            "impact":     "Completing coding restores reimbursement eligibility",
            "confidence": 0.90,
        })

        recs.append({
            "rank":       3,
            "action":     "Re-run INACBG grouper after iDRG completion",
            "reason":     "INACBG grouping requires a finalized iDRG result. Run grouper again after corrections.",
            "impact":     f"Expected reimbursement: IDR {financial.get('reimbursement_amount', 0):,.0f} "
                           "after successful regrouping",
            "confidence": 0.85,
        })

        return recs

    def _build_recommendations_for_invalid(
        self,
        prediction: Dict[str, Any],
        financial: Dict[str, Any],
        explanation: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Build recommendations when grouping_invalid is predicted.
        This is the highest-urgency outcome — full revenue at risk.

        Args:
            prediction:  prediction_result dict.
            financial:   financial_result dict.
            explanation: SHAP feature list.

        Returns:
            list of recommendation dicts.
        """
        top_feature    = explanation[0].get("feature") if explanation else None
        estimated_loss = financial.get("estimated_loss_idr", 0)
        delay_days     = financial.get("cash_flow_risk_days", 90)
        pred_conf      = prediction.get("confidence", {}).get("grouping_invalid", 0)

        if top_feature and top_feature in FEATURE_ACTION_MAP:
            cause_detail = FEATURE_ACTION_MAP[top_feature]
        else:
            cause_detail = "ICD-10 code failed INACBG validation — check against ICD-10 2010 reference"

        recs = [
            {
                "rank":       1,
                "action":     "Recode primary ICD-10 diagnosis",
                "reason":     f"INACBG grouping failed. Root cause: {cause_detail}.",
                "impact":     f"Revenue at risk: IDR {estimated_loss:,.0f}. Recoding required immediately.",
                "confidence": round(pred_conf, 4),
            },
            {
                "rank":       2,
                "action":     "Verify ICD-10 code against INA-CBGs 2010 reference",
                "reason":     "Invalid ICD-10 codes cause INACBG grouper to reject the claim entirely.",
                "impact":     "Correcting ICD-10 is the only path to reimbursement",
                "confidence": 0.95,
            },
            {
                "rank":       3,
                "action":     "Re-run full grouping cycle after correction (iDRG → INACBG)",
                "reason":     "Both groupers must succeed for claim to be valid. Correct ICD → re-run both.",
                "impact":     f"Expected resolution: {delay_days} days. Estimated reimbursement if corrected: "
                               f"IDR {financial.get('reimbursement_amount', 0):,.0f}",
                "confidence": 0.80,
            },
        ]
        return recs

    # ── Warning and tip builders ───────────────────────────────────────────────

    def _build_warnings(self, financial: Dict[str, Any]) -> List[str]:
        """
        Generate financial compliance warnings based on the financial assessment.

        Args:
            financial: financial_result dict from FinancialEstimator.

        Returns:
            list of warning strings.
        """
        warnings = []
        risk_level = financial.get("risk_level", "LOW")
        gap        = financial.get("financial_gap", 0)
        reimb_prob = financial.get("reimbursement_probability", 1.0)

        if risk_level == "CRITICAL":
            warnings.append(
                "CRITICAL: Grouping invalid — BPJS will not process this claim. "
                "Full revenue at risk until recoding and resubmission."
            )
        elif risk_level == "HIGH" and financial.get("estimated_loss_idr", 0) > 0:
            warnings.append(
                f"HIGH RISK: IDR {financial.get('estimated_loss_idr', 0):,.0f} "
                "exceeds INA-CBGs reimbursement ceiling and will NOT be reimbursed."
            )
        elif risk_level == "MEDIUM" and gap > 0:
            warnings.append(
                f"MEDIUM RISK: Tariff gap of IDR {gap:,.0f} will be absorbed by the hospital."
            )

        if reimb_prob < 0.50:
            warnings.append(
                f"Low reimbursement probability ({reimb_prob:.0%}). "
                "Escalate to senior Casemix coder for review."
            )

        return warnings

    def _generate_coding_tips(self, icd10_code: str, grouping_outcome: str) -> List[str]:
        """
        Provide ICD-10-specific coding tips relevant to the predicted outcome.
        Tips are derived from common Casemix pitfalls in BPJS/INA-CBGs practice.

        Args:
            icd10_code:       Primary ICD-10 code (e.g. "I10", "J18.0").
            grouping_outcome: Predicted outcome (used to add outcome-specific tips).

        Returns:
            list of coding tip strings.
        """
        tips = []
        code_upper = icd10_code.strip().upper()

        # Match by prefix (longest match first)
        for prefix in sorted(ICD10_CODING_TIPS.keys(), key=len, reverse=True):
            if code_upper.startswith(prefix):
                tips.append(ICD10_CODING_TIPS[prefix])
                break

        if not tips:
            tips.append("Verify ICD-10 code matches clinical documentation and is in ICD-10 2010 version")

        # Outcome-specific general tips
        if grouping_outcome == "grouping_invalid":
            tips.append(
                "For grouping failures: cross-reference ICD-10 code with the official "
                "INA-CBGs/INACBG reference — some codes valid in ICD-10 2016 are not in 2010 version"
            )
        elif grouping_outcome == "coding_incomplete":
            tips.append(
                "Ensure both iDRG finalization AND INACBG grouping steps are completed "
                "in sequence — INACBG will fail if iDRG is not finalized first"
            )

        return tips

    def _build_summary(
        self, grouping_outcome: str, risk_level: str, financial: Dict[str, Any]
    ) -> str:
        """
        Generate a one-sentence executive summary for the DSS dashboard header.

        Args:
            grouping_outcome: Predicted grouping outcome.
            risk_level:       Financial risk level.
            financial:        financial_result dict.

        Returns:
            str: Executive summary sentence.
        """
        reimb = financial.get("reimbursement_amount", 0)
        loss  = financial.get("estimated_loss_idr", 0)

        if grouping_outcome == "grouping_valid" and risk_level == "LOW":
            return f"Claim is ready for BPJS submission with low financial risk (IDR {reimb:,.0f} expected)."
        if grouping_outcome == "grouping_valid" and risk_level == "MEDIUM":
            return (
                f"Claim is valid and can be submitted; note IDR {loss:,.0f} tariff excess "
                "will not be reimbursed."
            )
        if grouping_outcome == "grouping_valid" and risk_level == "HIGH":
            return (
                f"Claim is valid but high tariff excess of IDR {loss:,.0f} — "
                "review tariff before submitting to BPJS."
            )
        if grouping_outcome == "coding_incomplete":
            return (
                "iDRG coding is incomplete — complete coding and re-run INACBG grouper "
                "before submission."
            )
        # grouping_invalid
        return (
            f"URGENT: INACBG grouping failed — IDR {loss:,.0f} at risk. "
            "Recode primary ICD-10 and resubmit immediately."
        )
