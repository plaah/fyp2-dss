#!/usr/bin/env python3
"""
Live browser screenshot test for FYP2 DSS doctor agent cases.
Uses Playwright to open the web UI, fill each test case, and capture screenshots.

Usage:
    source venv/bin/activate
    python scripts/screenshot_doctor_tests.py
"""

import asyncio, requests, sys
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright

FLASK_URL  = "http://127.0.0.1:5001"
SHOT_DIR   = Path("docs/test_reports/screenshots")
SHOT_DIR.mkdir(parents=True, exist_ok=True)

TIMESTAMP  = datetime.now().strftime("%Y%m%d_%H%M%S")

# Each case: (label, diag_text, proc_text, care_type value, kelas value, tariff)
CASES = [
    ("Case1_Hipertensi",   "hipertensi",       "tensi",          "outp", "kelas_3",  "196100"),
    ("Case2_Pneumonia",    "pneumonia",         "nebulisasi",     "inp",  "kelas_3",  "3613600"),
    ("Case3_DM_Neuropati", "diabetes melitus",  "tensi",          "inp",  "kelas_3",  "3611500"),
    ("Case4_BPH_TURP",     "bph prostat",       "turp",           "inp",  "kelas_3",  "7116300"),
    ("Case5_Stroke",       "stroke",            "fisioterapi",    "inp",  "kelas_3",  "5484100"),
    ("Case6_ISPA",         "ispa",              "tensi",          "outp", "kelas_3",  "150900"),
    ("Case7_Overcoding",   "hipertensi",        "tensi",          "outp", "kelas_3",  "500000"),
    ("Case8_Katarak",      "katarak",           "phaco",             "inp",  "kelas_3",  "3638300"),
]


async def screenshot_case(page, label, diag, proc, care_type, kelas, tariff):
    await page.goto(FLASK_URL, wait_until="networkidle")
    await page.wait_for_timeout(600)

    # Fill diagnosis
    await page.fill("#diag-input", "")
    await page.type("#diag-input", diag, delay=60)
    await page.wait_for_timeout(700)  # wait for pills

    # Click first pill if available, otherwise leave as-is (auto-resolve on submit)
    pills = await page.query_selector_all("#diag-pills .icd-pill")
    if pills:
        await pills[0].click()
        await page.wait_for_timeout(300)

    # Fill procedure
    await page.fill("#proc-input", "")
    await page.type("#proc-input", proc, delay=60)
    await page.wait_for_timeout(700)
    proc_pills = await page.query_selector_all("#proc-pills .icd-pill")
    if proc_pills:
        await proc_pills[0].click()
        await page.wait_for_timeout(300)

    # Set care_type and kelas
    await page.select_option("#care_type", care_type)
    await page.select_option("#kelas", kelas)

    # Fill tariff
    await page.fill("#actual_tariff", tariff)

    # Screenshot: form filled, before submit
    shot_before = SHOT_DIR / f"{TIMESTAMP}_{label}_1_form.png"
    await page.screenshot(path=str(shot_before), full_page=False)
    print(f"  📸 Form screenshot: {shot_before.name}")

    # Submit
    await page.click("#submit-btn")
    await page.wait_for_timeout(4000)  # wait for API + render

    # Screenshot: result rendered
    shot_after = SHOT_DIR / f"{TIMESTAMP}_{label}_2_result.png"
    await page.screenshot(path=str(shot_after), full_page=True)
    print(f"  📸 Result screenshot: {shot_after.name}")

    # Extract result values from DOM
    cbg_text    = await page.text_content("#cbg-headline")   or ""
    base_tariff = await page.text_content("#res-base-tariff") or ""
    kelas_ceil  = await page.text_content("#res-kelas-tariff") or ""
    status_txt  = await page.text_content("#res-tariff-status") or ""
    risk_txt    = await page.text_content("#res-risk")        or ""
    summary     = await page.text_content("#res-summary")     or ""

    return {
        "cbg": cbg_text.strip(),
        "base_tariff": base_tariff.strip(),
        "kelas_ceiling": kelas_ceil.strip(),
        "tariff_status": status_txt.strip(),
        "risk": risk_txt.strip(),
        "summary": summary.strip()[:120],
        "shot_form":   str(shot_before),
        "shot_result": str(shot_after),
    }


async def main():
    print("=" * 60)
    print("  FYP2 DSS — Live Browser Screenshot Tests")
    print(f"  {FLASK_URL}")
    print("=" * 60)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 900})
        page    = await context.new_page()

        report_lines = [
            "=== LIVE BROWSER TEST REPORT — Dr. Budi Santoso ===",
            f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"URL:  {FLASK_URL}",
            f"Screenshots: docs/test_reports/screenshots/",
            "",
        ]

        for label, diag, proc, care, kelas, tariff in CASES:
            print(f"\n[{label}]")
            print(f"  diag={diag!r}  proc={proc!r}  care={care}  tariff={tariff}")
            try:
                result = await screenshot_case(page, label, diag, proc, care, kelas, tariff)
                cbg_val = result["cbg"]
                risk_val = result["risk"]

                # Simple validation
                has_cbg = bool(cbg_val) and "?" not in cbg_val and "—" not in cbg_val
                status  = "✅ PASS" if has_cbg else "⚠️  WARN"

                print(f"  CBG:    {cbg_val}")
                print(f"  Risk:   {risk_val}")
                print(f"  Status: {status}")

                report_lines += [
                    f"[{label}]",
                    f"  Status:         {status}",
                    f"  CBG Predicted:  {cbg_val}",
                    f"  Base Tariff:    {result['base_tariff']}",
                    f"  BPJS Ceiling:   {result['kelas_ceiling']}",
                    f"  Tariff Status:  {result['tariff_status']}",
                    f"  Risk:           {risk_val}",
                    f"  Summary:        {result['summary']}",
                    f"  Screenshot form:   {Path(result['shot_form']).name}",
                    f"  Screenshot result: {Path(result['shot_result']).name}",
                    "",
                ]
            except Exception as e:
                print(f"  ERROR: {e}")
                report_lines += [f"[{label}] ERROR: {e}", ""]

        await browser.close()

    # Save report
    report_path = SHOT_DIR / f"{TIMESTAMP}_live_test_report.md"
    report_path.write_text("\n".join(report_lines))
    print(f"\n{'='*60}")
    print(f"Report + {len(CASES)*2} screenshots saved to:")
    print(f"  {SHOT_DIR}")
    print(f"{'='*60}")

    # Print report
    print()
    for l in report_lines:
        print(l)


if __name__ == "__main__":
    asyncio.run(main())
