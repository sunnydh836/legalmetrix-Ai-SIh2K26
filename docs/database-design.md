# LegalMetrix AI — Database Design

## 1. Relational Entity Relationship Diagram

```mermaid
erDiagram
    USERS ||--o{ SCAN_SESSIONS : "inspects"
    USERS ||--o{ AUDIT_LOGS : "performs"
    PRODUCTS ||--o{ SCAN_SESSIONS : "has"
    SCAN_SESSIONS ||--o{ SCAN_IMAGES : "contains"
    SCAN_SESSIONS ||--o{ DECLARATIONS : "has"
    SCAN_SESSIONS ||--o{ COMPLIANCE_FINDINGS : "evaluates_to"
    SCAN_SESSIONS ||--o{ REPORTS : "generates"
    SCAN_IMAGES ||--o{ OCR_BLOCKS : "yields"
    OCR_BLOCKS ||--o| DECLARATIONS : "sources"
    COMPLIANCE_RULES ||--o{ COMPLIANCE_FINDINGS : "defines"

    USERS {
        string id PK
        string email UK
        string full_name
        string role
        boolean is_active
        timestamp created_at
        timestamp updated_at
    }

    PRODUCTS {
        string id PK
        string name
        string brand
        string category
        string barcode UK
        string manufacturer_name
        timestamp created_at
        timestamp updated_at
    }

    SCAN_SESSIONS {
        string id PK
        string scan_code UK
        string product_id FK
        string inspector_id FK
        string status
        timestamp created_at
        timestamp updated_at
    }

    SCAN_IMAGES {
        string id PK
        string scan_session_id FK
        string image_type
        string file_path
        string original_filename
        string mime_type
        int file_size
        int width
        int height
        timestamp created_at
    }

    OCR_BLOCKS {
        string id PK
        string scan_image_id FK
        text text
        float confidence
        int bbox_x1
        int bbox_y1
        int bbox_x2
        int bbox_y2
        string ocr_engine
        string ocr_engine_version
        timestamp created_at
    }

    DECLARATIONS {
        string id PK
        string scan_session_id FK
        string declaration_type
        text raw_text
        jsonb normalized_value
        float confidence
        string source_ocr_block_id FK
        boolean reviewed
        jsonb reviewed_value
        timestamp created_at
    }

    COMPLIANCE_RULES {
        string id PK
        string rule_code
        string name
        text description
        string declaration_type
        string rule_version
        string severity
        boolean is_active
        jsonb rule_definition
        timestamp valid_from
        timestamp valid_to
        timestamp created_at
    }

    COMPLIANCE_FINDINGS {
        string id PK
        string scan_session_id FK
        string rule_id FK
        string rule_code
        string rule_version
        string status
        string reason_code
        text message
        jsonb detected_value
        jsonb expected_requirement
        float confidence
        jsonb evidence_reference
        timestamp created_at
    }

    REPORTS {
        string id PK
        string scan_session_id FK
        int version
        string status
        string file_path
        timestamp created_at
    }

    AUDIT_LOGS {
        string id PK
        string user_id FK
        string action
        string entity_type
        string entity_id
        jsonb metadata
        timestamp created_at
    }
```

---

## 2. Table Specifications & Indexing Strategy

1. **`users`**:
   - `id`: Primary key (UUID string)
   - `email`: Indexed unique string
   - `role`: Enum (`ADMIN`, `INSPECTOR`, `REVIEWER`)
2. **`products`**:
   - Indexed on `barcode` (unique), `name`, `brand`, `category` for rapid lookup during barcode scans.
3. **`scan_sessions`**:
   - Indexed on `scan_code` (unique), `product_id`, `inspector_id`, and `status`.
4. **`scan_images`**:
   - Indexed on `scan_session_id`.
5. **`ocr_blocks`**:
   - Indexed on `scan_image_id`. Coordinates (`bbox_x1`, `bbox_y1`, `bbox_x2`, `bbox_y2`) store region pixels.
6. **`declarations`**:
   - Indexed on `scan_session_id` and `declaration_type`.
   - `normalized_value` stores typed JSON (e.g. `{amount: 120, currency: "INR"}`).
   - Separate `reviewed` flag and `reviewed_value` ensure full audit trail separating machine extractions from human overrides.
7. **`compliance_rules`**:
   - Unique composite constraint on `(rule_code, rule_version)`.
   - `rule_definition` (JSONB) defines the exact deterministic conditions executed by the engine.
8. **`compliance_findings`**:
   - Indexed on `scan_session_id`, `rule_id`, `rule_code`, and `status`.
   - Retains immutable snapshots of `rule_code`, `rule_version`, `detected_value`, and `expected_requirement`.
9. **`reports`**:
   - Indexed on `scan_session_id`.
10. **`audit_logs`**:
   - Indexed on `user_id`, `action`, `entity_type`, `entity_id`.

---

## 3. Migration Strategy
Migrations are managed strictly via **Alembic** (`backend/alembic/versions/`). No direct schema manipulation via raw DDL is permitted in production environments.
