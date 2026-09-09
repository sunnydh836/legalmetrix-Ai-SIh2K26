# Authentication and Role-Based Access Control (RBAC) Specification

> **LegalMetrix AI (SIH26034) — Day 2 Architecture Documentation**

---

## 1. Overview & Security Philosophy

LegalMetrix AI operates as a government-grade enforcement platform for the **Legal Metrology (Packaged Commodities) Rules, 2011**. 

### Primary Security Principle
**Frontend role checks are purely for User Experience (UX); real authorization is strictly enforced at the FastAPI backend level.**
- Hiding navigation links in the React sidebar does not secure an endpoint.
- If an unauthorized client directly invokes an Admin or restricted endpoint, FastAPI immediately halts execution and returns an HTTP `403 Forbidden` response.
- Authentication failures (missing, invalid, or expired tokens) strictly return HTTP `401 Unauthorized`.

---

## 2. Role Taxonomy & Permission Matrix

The platform classifies users into three distinct roles:

| Role | Description | Allowed Frontend Views | Backend Capabilities |
| :--- | :--- | :--- | :--- |
| **`ADMIN`** | System & Legal Governance Administrator | Dashboard, Products, Inspections, Reports, Rule Library | Full platform control, User management, Rule editing & versioning |
| **`INSPECTOR`** | Field Enforcement Officer | Dashboard, New Scan (Capture/Upload), Products, Inspections, Reports | Image upload, OCR trigger, inspection generation |
| **`REVIEWER`** | Legal Metrology Adjudication Officer | Dashboard, Products, Inspections, Reports | Declaration review, compliance verdict adjudication |

### Detailed Route Permission Matrix

| Route | `ADMIN` | `INSPECTOR` | `REVIEWER` | Backend RBAC Dependency |
| :--- | :---: | :---: | :---: | :--- |
| `/dashboard` | Granted | Granted | Granted | `get_current_active_user` |
| `/scans/new` | Granted | Granted | Denied (403) | `require_roles(ADMIN, INSPECTOR)` |
| `/products` | Granted | Granted | Granted | `get_current_active_user` |
| `/products/:id` | Granted | Granted | Granted | `get_current_active_user` |
| `/inspections/:id` | Granted | Granted | Granted | `get_current_active_user` |
| `/reports` | Granted | Granted | Granted | `get_current_active_user` |
| `/rules` | Granted | Denied (403) | Denied (403) | `require_roles(ADMIN)` |
| `/api/v1/auth/users` | Granted | Denied (403) | Denied (403) | `require_roles(ADMIN)` |

---

## 3. Password Security & Storage

- **Algorithm**: **Argon2id** (memory-hard, resistant to GPU/ASIC brute-force attacks) implemented via `pwdlib`.
- **Storage**: Plaintext passwords are **never** stored, logged, or serialized into API responses. Only the one-way cryptographic hash (`password_hash`) is stored in the `users` table.
- **Verification**: Constant-time verification using `pwd_context.verify(plain, hash)` prevents timing attacks.

---

## 4. JWT Architecture & Token Flow

1. **Login**: User submits `POST /api/v1/auth/login` with email and password.
2. **Verification**: FastAPI authenticates credentials against the database.
3. **Issuance**: A signed JWT access token is returned with HMAC-SHA256 (`HS256`).
4. **Token Claims**:
   - `sub`: Unique user ID (e.g., `usr-admin-001` or UUID)
   - `email`: Normalized user email
   - `role`: Canonical role (`ADMIN`, `INSPECTOR`, or `REVIEWER`)
   - `iat`: Issued-at UTC timestamp
   - `exp`: Expiration UTC timestamp (default: 60 minutes)
5. **Consumption**: Frontend attaches token via `Authorization: Bearer <token>` in Axios request interceptors.

---

## 5. Audit Logging Architecture

All security-critical authentication and authorization events are immutably written to the `audit_logs` table via `app.services.audit_service.log_audit_event`:

| Action | Entity Type | Metadata Logged |
| :--- | :--- | :--- |
| `LOGIN_SUCCESS` | `USER` | User ID, email, role, timestamp |
| `LOGIN_FAILED` | `USER` | Sanitized email, failure reason |
| `LOGOUT` | `USER` | User ID, email, timestamp |
| `ACCESS_DENIED` | `ROUTE` | User ID, attempted role, required roles |
| `USER_CREATED` | `USER` | Admin ID, created user ID, assigned role |

> **Security Rule**: Audit metadata never stores plaintext passwords, raw tokens, or secret keys.

---

## 6. Frontend Authentication State & Route Protection

- **`AuthProvider` & `useAuth()`**: React Context maintaining `user`, `token`, `isAuthenticated`, and `isLoading`.
- **Session Hydration**: On app mount, the client checks stored credentials against `GET /api/v1/auth/me`. If valid, the session is hydrated; if invalid or expired, the local session is cleared and the user is redirected to `/login`.
- **`ProtectedRoute`**:
  - Displays loading skeleton during verification (eliminates protected content flash).
  - Redirects unauthenticated users to `/login` (preserving target path).
  - Redirects authenticated users lacking the required role to `/unauthorized`.
- **Axios Interceptor**:
  - Global `401` handler clears session and triggers login redirect.
  - Global `403` handler retains session while signaling access restriction.

---

## 7. Development Seed Accounts

For local development and testing, run:
```bash
python scripts/seed_users.py
```

| Role | Email | Default Development Password |
| :--- | :--- | :--- |
| **ADMIN** | `admin@legalmetrix.local` | `ChangeMeAdmin123!` |
| **INSPECTOR** | `inspector@legalmetrix.local` | `ChangeMeInspector123!` |
| **REVIEWER** | `reviewer@legalmetrix.local` | `ChangeMeReviewer123!` |

> **Notice**: These credentials are for local development only and must be overridden in production via environment variables.

---

## 8. Known Day 2 Limitations

- Token refresh rotation (refresh tokens) and blacklist caching will be introduced in production hardening.
- Server-side active session revocation is handled via user deactivation (`is_active = False`) and token expiration.
- Application business views (Product details, OCR scans, Rule editing) currently retain Day 1 domain structures until Day 3+ integrations.
