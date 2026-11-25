# Healthy API Integration

## Postman Integration Guide

This document is a practical guide for testing the `healthy_api` module from Postman. It is based on the current implementation in `controllers/api.py` and is written for business users, testers, and integration teams who need a clear request flow instead of a raw technical code dump.

## What This API Does

The module exposes an HTTP API for:

- user authentication with a daily access token
- user and signup approval management
- merchant management
- product and stock visibility
- sales order creation and status updates
- invoice, payment, return, and custody collection flows
- merchant visit tracking and itinerary retrieval
- API rule creation and assignment to users

## Base URL

Use your server base URL:

```text
{{base_url}}
```

Example:

```text
https://your-domain.com
```

## Postman Environment Variables

Create these variables in Postman before testing:

- `base_url`
- `token`
- `user_id`
- `merchant_id`
- `order_id`
- `invoice_id`
- `rule_id`

## Authentication Model

Most endpoints require a valid daily token.

The API accepts the token in one of the following ways:

- `Authorization: {{token}}`
- `token: {{token}}`
- query string: `?token={{token}}`

Recommended Postman header:

```text
Authorization: {{token}}
```

## Standard Response Format

Most routes return this envelope:

```json
{
  "data": {},
  "error": null
}
```

When an error occurs:

```json
{
  "data": null,
  "error": "Error message"
}
```

## Main Roles Used by the API

- `admin`: full access, user management, rule assignment, approvals
- `supervisor`: access to subordinate users and their related data
- `warehouse`: stock and warehouse-oriented operations
- `delegate`: field execution, merchants, visits, orders, collections

## Recommended Postman Flow

For a clean test cycle, use this order:

- login and store token
- create or identify a user
- create or identify a merchant
- create orders or payments
- create rules if needed
- assign rules to the target user

## Step 1: Login

Use this endpoint to obtain the daily token.

### Request

- Method: `POST`
- URL: `{{base_url}}/api/login`
- Headers:
  - `Content-Type: application/json`

```json
{
  "login": "admin@example.com",
  "password": "admin-password"
}
```

### Success Response

```json
{
  "data": {
    "token": "generated-daily-token",
    "uid": 3,
    "roles": ["Admin"],
    "user": {
      "id": 3,
      "name": "System Admin",
      "role": "Admin"
    }
  },
  "error": null
}
```

Save `data.token` into the Postman variable `token`.

## Step 2: Verify Access

You can confirm that the token works by calling:

- Method: `GET`
- URL: `{{base_url}}/api/users`
- Headers:
  - `Authorization: {{token}}`

If the token is valid, the route returns user data in your allowed scope.

## Endpoint Groups

## Authentication and Users

- `GET /api/users`
  - Returns users visible to the authenticated caller.
- `GET /api/daily_token`
  - Deprecated route. Use `/api/login`.
- `POST /auth/signup`
  - Creates a signup request that requires admin approval.
- `POST /api/login`
  - Authenticates user and returns a daily token.
- `GET|POST|PUT|DELETE /users`
  - Admin CRUD for users.
- `GET|PUT|DELETE /users/<user_id>`
  - User detail update or deletion.
- `PUT /users/<user_id>/approve`
  - Approves a user or pending signup request.
- `PUT /users/<user_id>/role`
  - Assigns roles such as `delegate`, `supervisor`, `warehouse`, `admin`.
- `GET|POST /api/admin/users`
  - Admin-oriented user listing and creation.
- `GET /api/admin/users/<user_id>`
  - Admin user detail.

## Merchants

- `GET|POST /api/merchants`
  - List merchants or create a merchant.
- `GET|PUT|DELETE /api/merchants/<merchant_id>`
  - Fetch, update, or delete a single merchant.

## Products and Stock

- `GET|POST /api/products`
  - Returns active saleable products or creates a new product.
- `GET|PUT|DELETE /api/products/<product_id>`
  - Returns, updates, or deletes a single product.
- `GET /api/stock`
  - Returns stock quantities by product and location.
- `GET /api/delivery_stock`
  - Returns stock assigned to a delivery user.
- `POST /api/delivery_stock/adjust`
  - Adjusts delivery-owned stock.
- `GET /api/warehouses`
  - Returns warehouse-related delivery records.
- `GET|PUT /api/inventory`
  - Reads or updates inventory.

## Orders

- `GET|POST /api/orders`
  - Reads or creates sale orders.
- `GET /api/orders/<order_id>`
  - Returns order detail.
- `PUT|DELETE /api/orders/<order_id>`
  - Updates or deletes an order.
- `POST /api/sale_orders/<order_id>/prepare`
  - Sets order warehouse status to prepared.
- `POST /api/sale_orders/<order_id>/ready`
  - Sets order status to ready.
- `POST /api/sale_orders/<order_id>/handover`
  - Sets order status to handover.
- `POST /api/sale_orders/<order_id>/deliver`
  - Sets order status to delivered.
- `POST /api/sale_orders/<order_id>/reject`
  - Rejects an order with optional reason.

## Invoices, Payments, Returns

- `GET|POST /api/payments`
  - Reads or creates customer payments.
- `GET /api/wallet_summary`
  - Returns collection summary.
- `GET|POST /api/invoices`
  - Reads or creates invoices.
- `GET|PUT|DELETE /api/invoices/<invoice_id>`
  - Invoice detail and update flow.
- `POST /api/invoices/<invoice_id>/upload_pdf`
  - Attaches a PDF file to an invoice.
- `GET|POST /api/returns`
  - Reads or creates returns / credit notes.
- `GET|POST /api/custody-funds`
  - Reads or registers collected custody funds.

## Signup Requests

- `GET /api/signup_requests`
  - Returns signup requests.
- `GET /api/signup_requests/<request_id>`
  - Returns one request.
- `POST /api/signup_requests/<request_id>/approve`
  - Approves the request and creates the user.
- `POST /api/signup_requests/<request_id>/reject`
  - Rejects the request.

## Visits and Routing

- `GET|POST /api/merchant_visits`
  - Creates or reads merchant visit records.
- `GET /api/itineraries`
  - Returns daily route data for a delegate.

## Offers

- `GET /api/offers`
  - Returns active pricelists and related rules.

## Rule Management

- `GET|POST /api/rules`
  - Reads all rules or creates a new rule.
- `PUT|DELETE /api/rules/<rule_id>`
  - Updates or deletes a rule.
- `PUT /api/users/<user_id>/rules`
  - Assigns one or more rule IDs to a user.

## Detailed Guide: Products Endpoint

The products API now supports full CRUD.

It can be used to:

- list the active saleable products
- read a single product
- create a new product
- update an existing product
- delete a product

This is useful in Postman when the mobile app or an external client needs a product catalog before creating orders or invoices, and when an admin needs to maintain product master data through the API.

### Route

- `GET {{base_url}}/api/products`
- `POST {{base_url}}/api/products`
- `GET {{base_url}}/api/products/{{product_id}}`
- `PUT {{base_url}}/api/products/{{product_id}}`
- `DELETE {{base_url}}/api/products/{{product_id}}`

### Authentication

This route requires a valid API token.

Headers:

- `Authorization: {{token}}`

### Permissions

- `GET /api/products`: any authenticated API user
- `GET /api/products/<product_id>`: any authenticated API user
- `POST /api/products`: admin only
- `PUT /api/products/<product_id>`: admin only
- `DELETE /api/products/<product_id>`: admin only

### Behavior

For product listing, the endpoint returns products where:

- `sale_ok = True`
- `active = True`

The controller returns these fields:

- `id`: product variant ID
- `template_id`: product template ID
- `name`: product display name
- `default_code`: internal reference or SKU
- `barcode`: barcode if available
- `price`: sale price from `lst_price`
- `tax_ids`: customer tax IDs linked to the product
- `active`: product active state
- `sale_ok`: whether the product is saleable
- `purchase_ok`: whether the product is purchasable
- `categ_id`: product category ID

### List Products Example

```text
GET {{base_url}}/api/products
```

Headers:

```text
Authorization: {{token}}
```

### Example Success Response

```json
{
  "data": [
    {
      "id": 101,
      "name": "Paracetamol 500mg",
      "default_code": "PARA-500",
      "barcode": "6223001234567",
      "price": 55.0,
      "tax_ids": [1, 3],
      "active": true
    },
    {
      "id": 102,
      "name": "Vitamin C 1000mg",
      "default_code": "VITC-1000",
      "barcode": "6223007654321",
      "price": 80.0,
      "tax_ids": [1],
      "active": true
    }
  ],
  "error": null
}
```

### Get One Product Example

```text
GET {{base_url}}/api/products/{{product_id}}
```

### Create Product Example

This is admin-only.

```text
POST {{base_url}}/api/products
```

```json
{
  "name": "Zinc 30mg",
  "default_code": "ZINC-30",
  "barcode": "6223005555555",
  "price": 95.0,
  "tax_ids": [1],
  "sale_ok": true,
  "purchase_ok": true,
  "active": true,
  "categ_id": 4
}
```

Example response:

```json
{
  "data": {
    "id": 145,
    "template_id": 145,
    "name": "Zinc 30mg",
    "default_code": "ZINC-30",
    "barcode": "6223005555555",
    "price": 95.0,
    "tax_ids": [1],
    "active": true,
    "sale_ok": true,
    "purchase_ok": true,
    "categ_id": 4
  },
  "error": null
}
```

### Update Product Example

This is admin-only.

```text
PUT {{base_url}}/api/products/{{product_id}}
```

```json
{
  "name": "Zinc 30mg Updated",
  "price": 99.0,
  "default_code": "ZINC-30-NEW",
  "barcode": "6223005555556",
  "tax_ids": [1, 3],
  "active": true,
  "sale_ok": true,
  "purchase_ok": true,
  "categ_id": 4
}
```

### Delete Product Example

This is admin-only.

```text
DELETE {{base_url}}/api/products/{{product_id}}
```

If the product has no linked records, it is deleted.

If linked records exist, the API archives it instead and returns:

```json
{
  "data": {
    "message": "Product archived (linked records prevent hard delete)"
  },
  "error": null
}
```

### When to Use It

Use `/api/products` before:

- creating sale orders
- creating invoices
- validating product IDs sent from mobile
- displaying a product catalog in an external app
- maintaining product master data from an admin integration

### Common Error Cases

If the token is missing or invalid:

```json
{
  "data": null,
  "error": "Unauthorized"
}
```

If a non-admin tries to create, edit, or delete a product:

```json
{
  "data": null,
  "error": "Forbidden"
}
```

If `categ_id` does not exist:

```json
{
  "data": null,
  "error": "Category not found"
}
```

If one or more `tax_ids` are invalid:

```json
{
  "data": null,
  "error": "One or more tax_ids are invalid"
}
```

## Detailed Guide: How to Assign a Rule to a User

This is the most important flow for Postman testing when rule-based access is used.

## Important Technical Prerequisite

The `api.rule` model must exist in the Odoo registry.

If the target server was updated with controller code but the module was not upgraded, the rules endpoints may fail or return a service error. The route now responds with a clear message when the model is missing:

```json
{
  "data": null,
  "error": "API rule model is not available. Upgrade the healthy_api module first."
}
```

Before testing rule assignment, confirm the following on the server:

- `models/api_rule.py` exists in the deployed module
- `models/__init__.py` imports `api_rule`
- the `healthy_api` module has been upgraded on the target database

## Rule Assignment Flow

Use this sequence in Postman.

### A. Login as an Admin User

Only an API admin can assign rules to a user.

#### Request

- Method: `POST`
- URL: `{{base_url}}/api/login`

```json
{
  "login": "admin@example.com",
  "password": "admin-password"
}
```

#### Postman action

Store the returned token in `{{token}}`.

### B. Create a Rule

#### Request

- Method: `POST`
- URL: `{{base_url}}/api/rules`
- Headers:
  - `Authorization: {{token}}`
  - `Content-Type: application/json`

```json
{
  "name": "Delegate Orders Only",
  "operations": {
    "orders": ["read", "create", "update"],
    "payments": ["read"],
    "merchants": ["read", "create"]
  }
}
```

#### Expected response

```json
{
  "data": {
    "id": 5,
    "name": "Delegate Orders Only",
    "operations": "{\"orders\": [\"read\", \"create\", \"update\"], \"payments\": [\"read\"], \"merchants\": [\"read\", \"create\"]}"
  },
  "error": null
}
```

Save `data.id` into the Postman variable `rule_id`.

### C. List Existing Rules

This step is useful when the rule already exists and you only need its ID.

#### Request

- Method: `GET`
- URL: `{{base_url}}/api/rules`
- Headers:
  - `Authorization: {{token}}`

#### Example response

```json
{
  "data": [
    {
      "id": 5,
      "name": "Delegate Orders Only",
      "operations": "{\"orders\": [\"read\", \"create\", \"update\"]}"
    }
  ],
  "error": null
}
```

### D. Assign the Rule to a User

This route writes the many-to-many relation `res.users.api_rule_ids`.

#### Request

- Method: `PUT`
- URL: `{{base_url}}/api/users/{{user_id}}/rules`
- Headers:
  - `Authorization: {{token}}`
  - `Content-Type: application/json`

```json
{
  "rule_ids": [5]
}
```

To assign more than one rule:

```json
{
  "rule_ids": [5, 6, 7]
}
```

#### Expected response

```json
{
  "data": {
    "id": 15,
    "name": "Ahmed Ali",
    "login": "ahmed@example.com",
    "role_key": "delegate",
    "roles": ["delegate"],
    "api_rules": [
      {
        "id": 5,
        "name": "Delegate Orders Only",
        "operations": "{\"orders\": [\"read\", \"create\", \"update\"]}"
      }
    ]
  },
  "error": null
}
```

### E. Verify the Assignment

Use one of these endpoints:

- `GET {{base_url}}/api/users`
- `GET {{base_url}}/api/admin/users/{{user_id}}`

In the response, confirm that `api_rules` contains the assigned rule.

## Common Error Cases for Rule Assignment

### Unauthorized

If the token is missing or invalid:

```json
{
  "data": null,
  "error": "Unauthorized"
}
```

### Forbidden

If the caller is not an admin:

```json
{
  "data": null,
  "error": "Forbidden"
}
```

### Invalid Payload

If `rule_ids` is missing or is not a JSON list:

```json
{
  "data": null,
  "error": "rule_ids must be a list"
}
```

### Invalid Rule IDs

If one or more rule IDs do not exist:

```json
{
  "data": null,
  "error": "One or more rule_ids are invalid"
}
```

### Missing Model

If the server registry does not contain `api.rule`:

```json
{
  "data": null,
  "error": "API rule model is not available. Upgrade the healthy_api module first."
}
```

## Useful Postman Request Examples

## Get Products

- Method: `GET`
- URL: `{{base_url}}/api/products`

Headers:

```text
Authorization: {{token}}
```

## Create Product

- Method: `POST`
- URL: `{{base_url}}/api/products`

```json
{
  "name": "Zinc 30mg",
  "default_code": "ZINC-30",
  "barcode": "6223005555555",
  "price": 95.0,
  "tax_ids": [1],
  "sale_ok": true,
  "purchase_ok": true,
  "active": true,
  "categ_id": 4
}
```

## Update Product

- Method: `PUT`
- URL: `{{base_url}}/api/products/{{product_id}}`

```json
{
  "price": 99.0,
  "default_code": "ZINC-30-NEW"
}
```

## Delete Product

- Method: `DELETE`
- URL: `{{base_url}}/api/products/{{product_id}}`

## Create Merchant

- Method: `POST`
- URL: `{{base_url}}/api/merchants`

```json
{
  "name": "Healthy Pharmacy",
  "mobile": "01011111111",
  "address": "Nasr City",
  "tax_card": "123456789",
  "assigned_user_id": 15
}
```

## Create Order

- Method: `POST`
- URL: `{{base_url}}/api/orders`

```json
{
  "merchant_id": 22,
  "user_id": 15,
  "lines": [
    {
      "product_id": 101,
      "quantity": 2,
      "price_unit": 55
    }
  ]
}
```

## Create Payment

- Method: `POST`
- URL: `{{base_url}}/api/payments`

```json
{
  "partner_id": 22,
  "amount": 500,
  "date": "2026-04-11"
}
```

## Upload Invoice PDF

- Method: `POST`
- URL: `{{base_url}}/api/invoices/{{invoice_id}}/upload_pdf`

Use one of these formats:

- form-data with a file field named `file`
- JSON body containing a base64 string in `pdf`

## Testing Notes

- Prefer `/api/...` routes when both `/api/...` and non-`/api/...` versions exist.
- Use an admin token when testing rules, user approval, and role assignment.
- The API is implemented as `type='http'`, so make sure Postman sends raw JSON where a body is expected.
- If a route suddenly returns a server-side model error, first verify that the module was upgraded after the latest code deployment.

## Maintenance Reference

The rule assignment feature relies on:

- model: `api.rule`
- relation field: `res.users.api_rule_ids`
- controller routes:
  - `POST /api/rules`
  - `GET /api/rules`
  - `PUT /api/rules/<rule_id>`
  - `DELETE /api/rules/<rule_id>`
  - `PUT /api/users/<user_id>/rules`

This guide should be regenerated if those routes or payloads change.
