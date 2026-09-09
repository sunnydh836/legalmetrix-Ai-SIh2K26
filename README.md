# LegalMetrix AI

> **AI-Assisted Packaged Commodity Declaration Inspection and Evidence Management System**  
> *Smart India Hackathon (SIH 2026)*

---

## Problem Statement

In India, all packaged commodities sold through retail or e-commerce channels must strictly comply with mandatory declaration standards governed by the **Legal Metrology (Packaged Commodities) Rules, 2011**. 

Manual inspection of package labels across thousands of SKUs is labor-intensive, error-prone, and challenging to scale. Inspectors must verify critical declarations across multiple product surfaces—including:
- Maximum Retail Price (MRP)
- Net Quantity & Unit Sale Price (USP)
- Manufacturer / Packer / Marketer details
- Date of Manufacture / Packing / Import
- Consumer Care contact details
- Country of Origin (for imported goods)

**LegalMetrix AI** assists inspectors by digitizing package evidence, validating photographic quality, running local OCR with bounding boxes, extracting and normalizing structured declaration candidates, and providing an interactive human-in-the-loop review workflow.

> [!NOTE]
> **Inspection-Assistance Model**: LegalMetrix AI serves as an evidence extractor and verification assistant for authorized inspectors. It digitizes evidence and flags potential discrepancies; final regulatory findings remain subject to human verification.

---

## Current Capabilities

The following features are implemented and active in the codebase:

- **Authentication & RBAC**:
  - Secure JWT authentication (`HS256`) with configurable token lifetime.
  - Argon2id password hashing via `pwdlib`.
  - 3-tier Role-Based Access Control (`ADMIN`, `INSPECTOR`, `REVIEWER`) strictly enforced at the API layer.
- **Product & Scan Session Management**:
  - Structured product registry with barcode indexing (`GET /api/v1/products/by-barcode/{barcode}`).
  - Multi-image package intake with panel classification (`FRONT`, `BACK`, `SIDE`, `TOP`, `BOTTOM`, `OTHER`).
  - Human-readable collision-safe scan session identifiers (`SCAN-YYYY-XXXXXX`).
  - Session image limits, file type verification (JPEG, PNG, WebP via Pillow), and payload size limits.
  - Automatic EXIF orientation normalization and duplicate image hash detection.
- **Image Quality Diagnostics**:
  - OpenCV-based blur detection via Laplacian variance analysis.
  - Glare and over-exposure detection using luminance thresholding.
  - Minimum resolution verification with automated warning badges (`PASS`, `WARNING`, `FAIL`).
- **OCR & Spatial Layout Engine**:
  - Local OCR extraction powered by `RapidOCR` / `PaddleOCR`.
  - Word/line bounding box coordinates, orientation angle classification, and confidence scoring.
  - Interactive frontend bounding-box overlay component.
- **Structured Declaration Candidate Extraction**:
  - Deterministic regex & pattern matching for key declaration fields:
    - MRP & Currency
    - Net Quantity & Measurement Units
    - Best Before / Expiry / Packaging Dates
    - Manufacturer / Packer / Marketer Names & Addresses
    - Consumer Care Email, Helpline Phone, and Physical Address
    - Country of Origin
    - FSSAI License Number (where applicable)
  - Text normalization, date parsing, and field-level confidence scoring.
- **Human-in-the-Loop Inspector Review**:
  - Dossier review interface allowing inspectors to confirm, edit, or reject candidate declarations.
  - Full audit logging of all authentication events, user operations, and inspection updates.

---

## System Architecture

```mermaid
flowchart TD
    subgraph Client["Inspector Web Portal (React + Vite)"]
        UI_Upload["Multi-Panel Image Upload\n(Front, Back, Sides)"]
        UI_Review["Dossier & Declaration Review\n(Confirm / Edit / Reject)"]
        UI_Dash["Inspector / Admin Dashboard"]
    end

    subgraph Backend["FastAPI Core Service"]
        API_Auth["Authentication & RBAC\n(JWT + Argon2id)"]
        API_Scans["Scan & Product Manager"]
        
        subgraph Pipeline["Evidence Processing Pipeline"]
            IQ_Engine["Image Quality Diagnostics\n(OpenCV Blur & Glare)"]
            OCR_Engine["OCR Layout Engine\n(RapidOCR / PaddleOCR)"]
            Extraction_Engine["Declaration Candidate Extractor\n(Pattern Matchers & Normalizers)"]
        end

        Audit["Immutable Audit Logger"]
    end

    subgraph Storage["Data & Storage Layer"]
        DB[(PostgreSQL 15+\nRelational & JSONB)]
        FileStore["Local Encrypted Storage\n(UUID Filenames)"]
    end

    UI_Upload -->|POST Images| API_Scans
    API_Scans --> FileStore
    API_Scans --> IQ_Engine
    IQ_Engine --> OCR_Engine
    OCR_Engine --> Extraction_Engine
    Extraction_Engine -->|Persist Blocks & Candidates| DB
    DB -->|Fetch Dossier & OCR Overlays| UI_Review
    UI_Review -->|Confirm / Modify Declarations| API_Scans
    API_Auth --> Audit
    API_Scans --> Audit
```

---

## Technology Stack

### Backend
- **Framework**: FastAPI (Python 3.10+)
- **ORM & Migrations**: SQLAlchemy 2.0, Alembic
- **Database**: PostgreSQL 15+ (with JSONB support)
- **Authentication**: PyJWT, `pwdlib` (Argon2id)
- **Computer Vision & OCR**: OpenCV (`opencv-python`), `rapidocr-onnxruntime`, `onnxruntime`, Pillow, NumPy
- **Validation**: Pydantic v2, Pydantic Settings

### Frontend
- **Framework**: React 18, Vite
- **Routing**: React Router v6
- **HTTP Client**: Axios
- **UI & Styling**: Tailwind CSS, Lucide Icons

---

## Project Structure

```
LegalMetrix AI/
├── .env.example                     # Root environment configuration guide
├── .gitignore                        # Git ignore rules for Python, Node, uploads, and secrets
├── README.md                         # Project documentation
├── backend/
│   ├── alembic/                      # Database migration scripts
│   │   ├── versions/                 # Versioned migration files (001 to 005)
│   │   └── env.py                    # Alembic environment runner
│   ├── alembic.ini                   # Alembic configuration
│   ├── app/
│   │   ├── api/                      # Central API routing & dependencies
│   │   ├── core/                     # App settings, DB session, security, enums
│   │   ├── models/                   # SQLAlchemy ORM models (Users, Scans, Declarations, etc.)
│   │   ├── routers/                  # FastAPI endpoint routers (auth, scans, declarations, products)
│   │   ├── schemas/                  # Pydantic request/response schemas
│   │   └── services/                 # Core domain logic
│   │       ├── audit_service.py      # Security & event audit logging
│   │       ├── auth_service.py       # Authentication & user management
│   │       ├── image_quality_service.py # OpenCV blur/glare diagnostics
│   │       ├── ocr_service.py        # OCR text & layout extractor
│   │       ├── scan_service.py       # Scan session lifecycle & storage
│   │       └── declaration_extraction/ # Candidate extraction & field normalizers
│   ├── benchmarks/ocr/               # OCR benchmark harness & CER/WER evaluation
│   ├── requirements.txt              # Backend Python dependencies
│   ├── scripts/                      # Utility & seed scripts
│   │   └── seed_users.py             # Idempotent development user seeder
│   ├── storage/                      # Runtime storage directory (ignored from git)
│   │   └── scans/                    # Uploaded package photos
│   └── tests/                        # Pytest automated test suite (103 tests)
├── docs/                             # Architecture & requirement specifications
└── frontend/
    ├── index.html                    # Frontend HTML entry
    ├── package.json                  # Frontend dependencies & scripts
    ├── vite.config.js                # Vite build configuration
    └── src/
        ├── components/               # UI components (UploadZone, OCR Overlay, Cards)
        ├── context/                  # AuthContext & state providers
        ├── layouts/                  # Main layout & navigation shell
        ├── pages/                    # Dashboard, NewScan, InspectionDetail, Products
        └── services/                 # Axios API service integrations
```

---

## Installation & Setup

### Prerequisites
- **Python**: 3.10, 3.11, or 3.12
- **Node.js**: 18+ and `npm`
- **PostgreSQL**: 15+ running locally or accessible via network

---

### 1. Clone the Repository

```bash
git clone https://github.com/<your-org-or-username>/LegalMetrix-AI.git
cd "LegalMetrix AI"
```

---

### 2. Backend Setup (Windows PowerShell / Command Prompt)

```powershell
# 1. Navigate to backend directory
cd backend

# 2. Create and activate a Python virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# 3. Upgrade pip and install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 4. Create local environment configuration
copy .env.example .env

# 5. Run database migrations to initialize tables
alembic upgrade head

# 6. Seed development users (idempotent)
python scripts/seed_users.py

# 7. Start the FastAPI development server
uvicorn app.main:app --reload --port 8000
```

- **API Base URL**: `http://localhost:8000`
- **Interactive Swagger Docs**: `http://localhost:8000/docs`
- **Health Endpoint**: `http://localhost:8000/health`

---

### 3. Frontend Setup

Open a separate terminal window:

```powershell
# 1. Navigate to frontend directory
cd frontend

# 2. Create local frontend environment configuration
copy .env.example .env

# 3. Install Node packages
npm install

# 4. Start Vite development server
npm run dev
```

- **Frontend Application URL**: `http://localhost:5173`

---

## Environment Variables

### Backend Configuration (`backend/.env`)

| Variable | Description | Safe Default / Placeholder |
| :--- | :--- | :--- |
| `APP_NAME` | Name of the application | `LegalMetrix AI` |
| `APP_ENV` | Application environment (`development` / `production`) | `development` |
| `API_V1_STR` | Versioned API route prefix | `/api/v1` |
| `DEBUG` | FastAPI debug flag | `True` |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+psycopg://postgres:password@localhost:5432/legalmetrix` |
| `SECRET_KEY` | Secret key for JWT signing | `change-me-in-production-legalmetrix-auth-secret-key-2026` |
| `JWT_ALGORITHM` | Algorithm for signing JWTs | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT expiration duration in minutes | `60` |
| `CORS_ORIGINS` | Comma-separated allowed frontend origins | `http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000` |
| `STORAGE_BACKEND` | Storage adapter (`local`) | `local` |
| `LOCAL_STORAGE_PATH` | Path for saving uploaded package images | `storage` |
| `MAX_UPLOAD_SIZE_MB` | Maximum allowed file size per image | `10` |
| `MAX_IMAGES_PER_SCAN` | Maximum images allowed per scan session | `8` |
| `OCR_ENGINE` | Active OCR engine (`paddleocr` / `rapidocr`) | `paddleocr` |
| `IMAGE_BLUR_THRESHOLD` | Minimum Laplacian variance threshold for sharpness | `100.0` |
| `IMAGE_GLARE_THRESHOLD` | Maximum allowable glare pixel ratio | `0.05` |
| `MIN_IMAGE_WIDTH` | Minimum acceptable image width (px) | `400` |
| `MIN_IMAGE_HEIGHT` | Minimum acceptable image height (px) | `400` |
| `OCR_LOW_CONFIDENCE_THRESHOLD`| Confidence threshold below which OCR flags a review warning | `0.60` |
| `OCR_USE_ANGLE_CLS` | Enable OCR orientation classification | `True` |
| `OCR_LANG` | OCR language code | `en` |

### Frontend Configuration (`frontend/.env`)

| Variable | Description | Default |
| :--- | :--- | :--- |
| `VITE_API_BASE_URL` | Backend API endpoint URL | `http://localhost:8000` |

---

## Development Seed Accounts

For local evaluation and testing, the idempotent seed script (`backend/scripts/seed_users.py`) provisions the following synthetic test accounts:

| Role | Email | Password (Development Default) | Primary Permissions |
| :--- | :--- | :--- | :--- |
| **`ADMIN`** | `admin@gmail.com` | `Admin123` | Full administrative control, user provisioning, system settings |
| **`INSPECTOR`** | `inspector@gmail.com` | `Inspector123` | Create scans, upload package images, edit candidate declarations |
| **`REVIEWER`** | `reviewer@gmail.com` | `Reviewer123` | View inspection dossiers, review evidence, verify compliance |

> [!WARNING]
> These credentials are strictly intended for local testing and development environments. Passwords and emails can be customized via `.env`.

---

## Running Tests

### Backend Automated Test Suite
The backend contains 103 unit and integration tests covering authentication, RBAC, scan workflows, image validation, OCR extraction, and schema contracts:

```powershell
cd backend
.\venv\Scripts\pytest.exe
```

### Frontend Production Build Test
Verify that frontend assets compile without bundling errors:

```powershell
cd frontend
npm run build
```

---

## Security & Compliance Considerations

- **Secrets Isolation**: No secret credentials or environment files are tracked in Git. All secrets are loaded strictly via environment variables.
- **Password Security**: Passwords are never stored in plaintext. They are hashed using the Argon2id key derivation function with salt.
- **JWT Protection**: Backend routes validate signature, expiry, and user role clearance on every protected request.
- **Path Traversal & File Intake Security**: Uploaded files are verified for valid image magic bytes (Pillow) and stored with randomized UUID filenames, avoiding path traversal vulnerabilities.
- **Audit Trails**: Security-critical actions (login attempts, permission rejections, user creation, inspection edits) generate immutable audit records with actor IDs and client IP information.

---

## Legal Disclaimer

> [!CAUTION]
> **LegalMetrix AI is an inspection-assistance research prototype.** Machine-extracted declarations and automated evaluations are designed to support human inspectors and must be reviewed by authorized personnel. This repository and its outputs do not constitute formal legal advice or authoritative legal adjudication under the Legal Metrology Act, 2009.

---

## Future Scope

The following features represent planned architectural extensions:
- **POS / Billing-System Integration**: Real-time integration with retail point-of-sale systems for automated barcode verification.
- **Barcode-Triggered Compliance Inspection**: Instant rule retrieval from national databases upon scanning EAN/UPC barcodes.
- **Automated Non-Compliance Notice Generation**: Automated generation of formal inspection notice drafts citing specific rules under the Legal Metrology (Packaged Commodities) Rules, 2011.
- **Mobile Edge Capture**: Native mobile camera capture with on-device orientation guidance and glare prevention.
- **Multilingual Regional Declaration Extraction**: Expansion of OCR and extraction models to support 22 official Indian regional languages.
