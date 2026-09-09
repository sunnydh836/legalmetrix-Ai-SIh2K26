# LegalMetrix AI — API Contract Documentation

This document outlines the REST API design for the LegalMetrix AI platform. All request/response bodies adhere to JSON schemas defined in `backend/app/schemas/`.

Base URL: `/api/v1`

---

## 1. System & Health

### `GET /`
- **Description**: Root status ping
- **Response**: `200 OK`
```json
{
  "name": "LegalMetrix AI API",
  "status": "running"
}
```

### `GET /health` & `GET /api/v1/health`
- **Description**: Liveness and readiness health probe
- **Response**: `200 OK`
```json
{
  "status": "healthy"
}
```

---

## 2. Authentication (Planned)

### `POST /auth/login`
- **Request**:
```json
{
  "email": "inspector@legalmetrology.gov.in",
  "password": "SecurePassword123!"
}
```
- **Response**: `200 OK`
```json
{
  "access_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "user": {
    "id": "u-01",
    "email": "inspector@legalmetrology.gov.in",
    "full_name": "Senior Inspector Sharma",
    "role": "INSPECTOR"
  }
}
```

### `GET /auth/me`
- **Description**: Retrieve active user profile

---

## 3. Scan Sessions & Images

### `POST /scans`
- **Request**:
```json
{
  "product_id": "p-12345",
  "inspector_id": "u-01"
}
```
- **Response**: `201 Created`
```json
{
  "id": "s-9988",
  "scan_code": "SCAN-20260905-9988",
  "status": "CREATED",
  "created_at": "2026-09-05T12:00:00Z",
  "images": []
}
```

### `GET /scans/{id}`
- **Description**: Retrieve full scan session details, images, declarations, and findings.

### `POST /scans/{id}/images`
- **Content-Type**: `multipart/form-data`
- **Fields**: `image_type` (FRONT/BACK/SIDE/OTHER), `file` (binary)

### `POST /scans/{id}/process`
- **Description**: Triggers quality check, OCR execution, declaration extraction, and rule evaluation.

---

## 4. OCR Inspection

### `GET /scans/{id}/ocr`
- **Response**: `200 OK`
```json
{
  "scan_image_id": "img-001",
  "engine": "paddleocr",
  "engine_version": "2.7.0",
  "blocks": [
    {
      "text": "MRP Rs. 120.00 (Incl. of all taxes)",
      "confidence": 0.96,
      "bbox": {
        "x1": 100,
        "y1": 250,
        "x2": 450,
        "y2": 290
      }
    }
  ]
}
```

---

## 5. Declarations

### `GET /scans/{id}/declarations`
- **Response**: `200 OK`
```json
[
  {
    "id": "decl-01",
    "scan_session_id": "s-9988",
    "declaration_type": "MRP",
    "raw_text": "MRP ₹120 incl. of all taxes",
    "normalized_value": {
      "amount": 120.0,
      "currency": "INR",
      "taxes_inclusive": true
    },
    "confidence": 0.94,
    "reviewed": false,
    "reviewed_value": null
  }
]
```

### `PUT /declarations/{id}`
- **Description**: Human inspector override/verification
- **Request**:
```json
{
  "reviewed": true,
  "reviewed_value": {
    "amount": 120.0,
    "currency": "INR",
    "verified_by": "u-01"
  }
}
```

---

## 6. Compliance Evaluation

### `POST /scans/{id}/evaluate`
- **Description**: Deterministically evaluates declarations against active rules.

### `GET /scans/{id}/compliance`
- **Response**: `200 OK`
```json
{
  "scan_session_id": "s-9988",
  "rule_set_version": "2011.1.0",
  "overall_status": "PASS",
  "total_rules_evaluated": 4,
  "passed_count": 4,
  "failed_count": 0,
  "review_count": 0,
  "not_applicable_count": 0,
  "findings": [
    {
      "id": "find-01",
      "rule_code": "LMR_2011_R06_MRP",
      "rule_version": "2011.1.0",
      "status": "PASS",
      "reason_code": "MRP_PRESENT",
      "message": "Valid declaration detected: MRP ₹120 incl. of all taxes",
      "detected_value": {"raw_text": "MRP ₹120 incl. of all taxes"},
      "expected_requirement": {"description": "MRP Rs. XX.XX inclusive of all taxes"},
      "confidence": 0.94,
      "evidence_reference": {"source_ocr_block_id": "block-001"}
    }
  ]
}
```

---

## 7. Reports

### `POST /scans/{id}/reports`
- **Description**: Generates an official inspection PDF/JSON report.

### `GET /reports/{id}`
- **Description**: Download/fetch generated report metadata.

---

## 8. Rule Library

### `GET /rules`
- **Description**: List all active and historical legal rules with version metadata.

### `POST /rules`
- **Description**: Add new compliance rule definition.

### `PUT /rules/{id}`
- **Description**: Update rule definition (creates a new version if modified).

---

## 9. Analytics & Dashboard

### `GET /analytics/summary`
- **Description**: Top-level KPI counts (total inspections, pass rate, review queue size).

### `GET /analytics/violations`
- **Description**: Frequent non-compliance breakdown by commodity category and rule code.

### `GET /analytics/trends`
- **Description**: Time-series compliance metrics.
