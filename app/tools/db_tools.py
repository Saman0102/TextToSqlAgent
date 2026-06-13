"""Database access helpers."""

from sqlalchemy import text

from app.core.config import settings
from app.core.db import get_engine


import re

MIXED_CASE_IDENTIFIERS = [
    "customerNumber", "orderNumber", "productCode", "productName", "productLine",
    "productScale", "productVendor", "productDescription", "quantityInStock",
    "buyPrice", "MSRP", "textDescription", "htmlDescription", "officeCode",
    "addressLine1", "addressLine2", "postalCode", "employeeNumber", "lastName",
    "firstName", "reportsTo", "jobTitle", "contactLastName", "contactFirstName",
    "salesRepEmployeeNumber", "creditLimit", "checkNumber", "paymentDate",
    "shippedDate", "requiredDate", "orderDate", "quantityOrdered", "priceEach",
    "orderLineNumber", "productlines", "orderdetails"
]


def quote_mixed_case_identifiers(sql: str) -> str:
    quoted_sql = sql
    for ident in MIXED_CASE_IDENTIFIERS:
        pattern = r'(?<!")\b' + re.escape(ident) + r'\b(?!")'
        quoted_sql = re.sub(pattern, f'"{ident}"', quoted_sql)
    return quoted_sql


def execute_readonly_query(sql: str, params: dict) -> list[dict]:
    sql_quoted = quote_mixed_case_identifiers(sql)
    with get_engine().connect() as conn:
        result = conn.execute(text(sql_quoted), params)
        rows = [dict(row._mapping) for row in result]

    if settings.max_rows and len(rows) > settings.max_rows:
        rows = rows[: settings.max_rows]

    return rows
