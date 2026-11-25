# Healthy API - Postman Guide

This guide documents all routes in `healthy_api/controllers/api.py` and how to call them from Postman.

## Mobile-Managed Integration (Scope)

This integration is fully managed by the mobile application.

- The mobile app drives the full lifecycle: signup request, admin approval, login, and daily operations.
- All business actions should be done through these API endpoints (not Odoo manual back-office operations).
- Every protected endpoint requires the daily token returned by login.
- Users must login from mobile first, then call other endpoints using `Authorization: Bearer <daily_token>`.

## 1) Postman Setup

Create these Postman variables:

- `base_url` = your Odoo host (example: `http://localhost:8069`)
- `token` = API token returned from login

For authenticated calls, add header:

- `Authorization: {{token}}`
- `Content-Type: application/json`

Public routes (no token):

- `POST {{base_url}}/auth/signup`
- `POST {{base_url}}/auth/login` (or `/api/login`)

## 2) Core Business Endpoints

### Auth

- `POST /auth/signup`
- `POST /auth/login` (alias: `POST /api/login`)

Signup body:
```json
{
  "name": "John Doe",
  "email": "john@example.com",
  "mobile": "+201234567890",
  "password": "StrongPassword123"
}
```

Login body:
```json
{
  "email_or_mobile": "john@example.com",
  "password": "StrongPassword123"
}
```

Login response returns the daily token in `data.token`.  
Use that token in `Authorization: <daily_token>` for all protected endpoints.

### Users & Roles (Admin)

- `GET /users`
- `GET /users/{id}`
- `POST /users`
- `PUT /users/{id}`
- `DELETE /users/{id}`
- `PUT /users/{id}/approve`
- `PUT /users/{id}/role`

Create/Update body example:
```json
{
  "name": "Area Manager 1",
  "email": "am1@example.com",
  "password": "StrongPassword123",
  "mobile": "+201111111111",
  "area_name": "Nasr City",
  "roles": ["area_manager"],
  "active": true
}
```

Assign role body:
```json
{
  "roles": ["delivery"]
}
```

### Merchants

- `GET /merchants` (alias: `/api/merchants`)
- `POST /merchants`
- `GET /merchants/{id}`
- `PUT /merchants/{id}`
- `DELETE /merchants/{id}` (Admin)

Create/Update body example:
```json
{
  "merchant_code": "M-1001",
  "name": "Merchant A",
  "mobile": "+201000000000",
  "address": "Cairo",
  "commercial_registration": "CR12345",
  "tax_card": "TAX56789"
}
```

### Orders

- `GET /orders` (alias: `/api/orders`)
- `GET /orders/{id}`
- `POST /orders`
- `PUT /orders/{id}`
- `DELETE /orders/{id}` (Admin)

Create body:
```json
{
  "merchant_id": 10,
  "order_date": "2026-03-31 10:30:00",
  "products": [
    {"product_id": 101, "quantity": 2, "price_unit": 50},
    {"product_id": 102, "quantity": 1}
  ]
}
```

Update status body example:
```json
{
  "status": "accepted"
}
```

Allowed flow: `pending -> accepted/rejected -> prepared -> delivered`.

### Inventory

- `GET /inventory` (alias: `/api/inventory`)
- `PUT /inventory`

`GET /inventory` returns: `order_id`, `area`, `status`.

Update body:
```json
{
  "order_id": 55,
  "status": "prepared",
  "reason": "optional"
}
```

### Invoices

- `GET /invoices` (alias: `/api/invoices`)
- `GET /invoices/{id}`
- `POST /invoices`

Body:
```json
{
  "order_id": 55,
  "merchant_id": 10,
  "payment_method": "cash",
  "products": [
    {"product_id": 101, "quantity": 2, "price_unit": 50}
  ]
}
```

### Return Invoices

- `GET /return-invoices` (aliases: `/api/returns`, `/api/return-invoices`)
- `GET /return-invoices/{id}`
- `POST /return-invoices`

Body:
```json
{
  "invoice_id": 88,
  "note": "Damaged items",
  "products": [
    {"product_id": 101, "quantity": 1, "price_unit": 50}
  ]
}
```

### Car Warehouse

- `GET /warehouses` (alias: `/api/warehouses`)

Auto-generated daily for authenticated delivery user.  
Fields: `order_id`, `delivery_id`, `products`, `quantity_available`.

### Itinerary

- `GET /itineraries` (alias: `/api/itineraries`)

Query params:

- `delivery_id` (optional for manager)
- `date=YYYY-MM-DD` (optional, default today)

Response fields: `delivery_id`, `merchant_locations`, `date`.

### Custody Funds

- `GET /custody-funds` (alias: `/api/custody-funds`)
- `POST /custody-funds`

GET params:

- `delivery_id` (optional, defaults to logged-in delivery)
- `date=YYYY-MM-DD` (optional)

POST body:
```json
{
  "delivery_id": 25,
  "partner_id": 10,
  "collected_amount": 500,
  "date": "2026-03-31"
}
```

Response fields: `delivery_id`, `collected_amount`, `date`.

## 3) Admin Approval Endpoints

These are still API-based and can be consumed by an admin mobile panel (or admin client):

- `GET /api/signup_requests/{id?}`
- `POST /api/signup_requests/{id}/approve`
- `POST /api/signup_requests/{id}/reject`

## 4) Common Postman Notes

- Use `Body -> raw -> JSON` for POST/PUT.
- For routes with `{id}`, replace with integer ID (example: `/orders/55`).
- If you get `401 Unauthorized`, refresh token with login and update `{{token}}`.
- If you get `403 Forbidden`, check user role and endpoint access matrix.
