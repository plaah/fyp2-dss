# Chapter 4: System Design

*(Sections 4.1–4.3 cover the system architecture, use case design, and data flow diagrams — to be completed in the full thesis submission. This draft covers Sections 4.4 and 4.5 as specified in Sprint 4.)*

---

## 4.4 Database Design

### 4.4.1 Overview of the Database Schema

The DSS employs a PostgreSQL relational database named `fyp2_db` to persist prediction results, maintain an ICD code reference catalogue, and store pre-aggregated analytics data. Three tables constitute the core schema: `predictions`, `icd_reference`, and `system_stats`. The schema was designed with two concurrent objectives in mind: supporting real-time audit trail requirements for clinical accountability, and enabling low-latency dashboard rendering without executing expensive aggregation queries on every page load.

SQLAlchemy's declarative ORM was selected over raw SQL queries for several reasons. First, the declarative model definition keeps the schema co-located with the Python domain model, reducing the risk of schema-code divergence as the system evolves. Second, SQLAlchemy's session management and unit-of-work pattern provides automatic transaction handling, which simplifies the non-blocking save pattern used by the `/full-assessment` endpoint. Third, the ORM enables database-agnostic development: the same model definitions can be applied to SQLite during unit testing or PostgreSQL in production without code changes.

### 4.4.2 The `predictions` Table

The `predictions` table is the central audit log of the system. Every call to the `/api/v1/full-assessment` endpoint automatically persists a row to this table, capturing the input claim parameters, the ML prediction outcome, the financial risk assessment, and the top SHAP feature that drove the prediction. This design ensures that every clinical decision made with the DSS assistance is traceable — a requirement in regulated healthcare informatics environments.

The table stores confidence scores for each of the three prediction classes (`confidence_valid`, `confidence_incomplete`, `confidence_invalid`), allowing retrospective calibration analysis of the model's uncertainty over time. The `top_shap_feature` column records the single most influential feature name from the SHAP explanation, providing a lightweight summary of the model's reasoning without storing the full SHAP vector. The `source` column is designed to accept either `'manual'` (Casemix coder entered the data through the web form) or `'neurovi'` (the data was fetched automatically from the Neurovi HIS), anticipating the future hospital information system integration described in Section 4.5.4.

### 4.4.3 The `icd_reference` Table

The `icd_reference` table stores the complete catalogue of ICD-10 2010 (WHO) diagnosis codes and ICD-9-CM procedure codes. Each row contains the code string, a human-readable description of up to 300 characters, a category flag (`icd10` or `icd9`) for query filtering, and an optional MDC group field linking the code to its Major Diagnostic Category in the INA-CBGs grouper. A unique constraint on the `code` column ensures referential integrity and enables O(1) lookup by code string, which is required for the real-time autocomplete functionality planned for Sprint 5.

The table is seeded from two reference files distributed with the project: `data/icd10_2010_reference.csv` and `data/icd9_cm_procedures.csv`. These files contain the official code sets used by BPJS Kesehatan for the INA-CBGs grouping engine, ensuring that the DSS validates ICD codes against the same reference as the official grouper.

### 4.4.4 The `system_stats` Table

The `system_stats` table stores pre-computed daily aggregate statistics for the analytics dashboard. Each row represents one calendar day and records the total prediction count, the per-label count breakdown, the average reimbursement probability, the total financial gap accumulated, and the most frequently submitted ICD-10 code. This pre-aggregation strategy is a deliberate performance design decision: computing these metrics live from the `predictions` table using `GROUP BY` and `SUM` across potentially thousands of rows on every dashboard page load would introduce unacceptable latency in a clinical environment. By pre-aggregating nightly (Sprint 5 will add the background scheduler), the dashboard can render KPI cards in a single indexed row lookup.

### 4.4.5 Entity-Relationship Overview

The three tables are loosely coupled rather than strictly normalised. The `predictions` table is self-contained and does not carry a foreign key to `icd_reference` — this is intentional. ICD codes entered by Casemix coders may contain minor variations (e.g., with or without trailing characters) that would fail a foreign key constraint and block prediction saving. Instead, code validation against `icd_reference` is a soft check surfaced as a warning in the recommendation output rather than a hard constraint enforced at the database layer. The `system_stats` table is also independent, populated by a separate aggregation job that reads from `predictions`. This decoupled architecture tolerates partial failures: a gap in the `system_stats` series does not corrupt the prediction audit log.

*[Note: A formal ERD diagram will be inserted here from the database visualisation tool in the final submission.]*

---

## 4.5 Interface Design

### 4.5.1 Design Philosophy and Target User

The user interface is designed for a specific, well-defined user type: the Casemix coder at an Indonesian hospital using the Neurovi HIS. Casemix coders are clinical billing specialists who work with ICD-10 diagnosis codes and ICD-9-CM procedure codes daily. They possess deep domain knowledge of the coding system but may not have technical backgrounds. The interface therefore prioritises speed of interaction and clarity of output over configurability. A Casemix coder must be able to enter a claim's ICD codes, receive a grouping prediction, and understand the recommended next action within seconds — without consulting any documentation.

Several explicit design decisions follow from this philosophy. The layout uses a predominantly white, clinical aesthetic rather than a dark theme, as white-dominant interfaces align with the visual conventions of hospital information systems that Casemix coders use daily. The prediction outcome — `Grouping Valid`, `Coding Incomplete`, or `Grouping Invalid` — is displayed as the largest, most visually prominent element on the page, ensuring that the primary answer to the coder's question is immediately visible without scrolling or reading paragraphs of text.

### 4.5.2 Color Coding Convention

The color scheme deliberately mirrors the traffic-light convention used in BPJS Kesehatan documentation and common hospital quality management systems. Green (`#22c55e`) represents `grouping_valid` — the claim is safe to submit to BPJS. Amber/yellow (`#f59e0b`) represents `coding_incomplete` — action is required but the situation is recoverable. Red (`#ef4444`) represents `grouping_invalid` — urgent recoding is required and revenue is at risk. This convention is applied consistently across all UI elements: the outcome badge, the recommendation box border, the table row color, and the risk badge text. The goal is that an experienced coder can assess the status of a claim at a glance from across the room, without reading any text.

Risk levels carry a secondary color system: LOW in green, MEDIUM in yellow, HIGH in orange (`#f97316`), and CRITICAL in red. The CRITICAL level uses the same red as `grouping_invalid` because the two states are semantically equivalent from a financial risk perspective.

### 4.5.3 Page 1 — ICD Grouping Prediction Tool (`/`)

The prediction tool page is structured into three vertically stacked sections. The first section contains the input form, presented as a clean white card with a subtle drop shadow. Form fields are arranged in a two-column responsive grid. ICD-10 diagnosis code fields are implemented as free-text inputs rather than dropdown selectors — a deliberate design choice based on the observation that experienced Casemix coders type ICD codes fluently from memory and find dropdown navigation slower than direct entry. The inputs are configured for automatic uppercase conversion to match the ICD-10 standard. Tariff fields accept numeric values in Indonesian Rupiah without a currency prefix in the input itself, reducing cognitive load during data entry.

The submit button is full-width, blue, and prominently sized to reduce the time from "ready to submit" to "result rendered". A small helper text below the button sets the expectation that results appear within one second, reducing uncertainty during the model inference latency window.

The second section — the result area — is hidden until a successful API response is received. It then animates into view with a smooth slide-in transition. The section is divided into four sub-components rendered sequentially: the prediction outcome badge (large, colored, with icon and label), the three-segment confidence bar showing the probability distribution across all three classes, three financial metric cards showing the reimbursement ceiling, financial gap, and reimbursement probability, and the SHAP horizontal bar chart displaying the top three prediction-driving features. Below these components, a recommendation box with a colored left border matches the prediction outcome color and presents the primary action badge, the ranked recommendation list, ICD-10 coding tips, and the estimated resolution timeline.

The third section is a live-updating table showing the ten most recent predictions from the current day. This serves two purposes: it allows the coder to review their recent work without navigating away, and it provides social proof that the system is actively recording decisions for audit purposes. Each row is color-coded by outcome class and shows the timestamp, primary ICD-10 code, prediction outcome, risk level, financial gap in IDR, and recommended action.

All monetary values are formatted using the `formatIDR()` JavaScript function, which applies the Indonesian locale convention: dots as thousand separators (e.g., `Rp 196.100`) rather than the Western comma convention. This is a minor but important detail for Indonesian clinical users, as incorrect currency formatting creates cognitive friction and reduces trust in the displayed values.

### 4.5.4 Page 2 — Analytics Dashboard (`/dashboard`)

The analytics dashboard provides a management-level view of system usage and financial risk trends. It is designed to be useful both to the Casemix coder team lead and to hospital finance administrators who may not interact with the prediction tool directly.

The page opens with a row of four KPI (Key Performance Indicator) cards showing the total prediction count, the grouping valid rate as a percentage, the average reimbursement probability, and the cumulative financial gap in IDR. These figures are pulled from the `/api/v1/stats` endpoint and rendered on page load without requiring any user interaction.

Below the KPI row, two charts are displayed side by side. The left chart is a doughnut chart showing the distribution of predictions across the three outcome labels, using the same green/amber/red color convention as the prediction page. The right chart is a multi-series line chart showing total predictions and valid-outcome predictions per day over the last seven days, allowing managers to identify trends in coding error rates over time.

The third section contains a grouped bar chart showing the risk distribution: how many claims were classified as LOW, MEDIUM, HIGH, and CRITICAL financial risk. This chart is particularly relevant to the hospital finance team, as it indicates the cumulative revenue absorption risk and the urgency of addressing pending recode cases.

The fourth section is a full paginated table of all stored predictions, displaying eight columns per row and paginated at twenty rows per page. A CSV export button in the page header allows a Casemix supervisor to download the complete prediction history for external reporting or quality audit submission.

### 4.5.5 Neurovi HIS Integration Preparation

The Neurovi HIS integration hook is prepared in the current implementation but not yet active, pending receipt of the Neurovi API documentation from Tamtech. The sidebar of both pages includes a disabled "Connect Neurovi" button as a visual affordance that communicates the planned integration to stakeholders viewing the system during Demo 1. When the Neurovi API documentation becomes available in Sprint 5, the `fetchFromNeurovi(encounterId)` stub function in `static/js/app.js` will be extended to auto-populate the prediction form's ICD-10, tariff, and care type fields from real encounter data. The `source` field in the `predictions` database table is already configured to accept the value `'neurovi'`, ensuring that predictions originating from the HIS integration will be distinguishable from manually entered predictions in the audit log.

*[Note: Screenshots of both pages will be inserted in Sections 4.5.3.x and 4.5.4.x after the system is demonstrated live in Demo 1.]*

---

*Word count by section:*
- 4.4.1 Database Overview: ~220 words
- 4.4.2 predictions table: ~200 words
- 4.4.3 icd_reference table: ~180 words
- 4.4.4 system_stats table: ~200 words
- 4.4.5 ERD Overview: ~180 words
- 4.5.1 Design Philosophy: ~220 words
- 4.5.2 Color Convention: ~180 words
- 4.5.3 Page 1: ~370 words
- 4.5.4 Page 2: ~250 words
- 4.5.5 Neurovi Hook: ~180 words
- **Total: ~2,180 words**
