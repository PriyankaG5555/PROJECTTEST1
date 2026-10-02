# API Contract Spec — Trip Planner

> Purpose: The single source of truth between frontend and backend. Both sides must conform exactly to this contract.

## 1. General Conventions
- **Base URL:** <!-- e.g., /api/v1 -->
- **Protocol / format:** <!-- REST + JSON -->
- **Authentication:** <!-- e.g., `Authorization: Bearer <token>` -->
- **Naming convention:** <!-- camelCase / snake_case -->
- **Date/time format:** <!-- e.g., ISO 8601 UTC -->
- **Pagination:** <!-- e.g., ?page=&limit= -->
- **Versioning:**

## 2. Standard Error Response
```json
{
  "error": {
    "code": "",
    "message": "",
    "details": {}
  }
}
```
| HTTP status | Code | When |
|-------------|------|------|
| 400 | VALIDATION_ERROR | |
| 401 | UNAUTHORIZED | |
| 403 | FORBIDDEN | |
| 404 | NOT_FOUND | |
| 500 | INTERNAL_ERROR | |

## 3. Shared Schemas
### <SchemaName>
```json
{
}
```

## 4. Endpoints Summary
| Method | Path | Description | Auth |
|--------|------|-------------|------|
|        |      |             |      |

## 5. Endpoint Details

### `<METHOD> <path>`
- **Description:**
- **Auth required:**
- **Path params:**
- **Query params:**

**Request body**
```json
{
}
```

**Success response — `200`**
```json
{
}
```

**Error responses**
| Status | Code | Condition |
|--------|------|-----------|
|        |      |           |

<!-- Copy the block above for each endpoint. -->

## 6. Change Log
| Date | Change | Author |
|------|--------|--------|
|      |        |        |
