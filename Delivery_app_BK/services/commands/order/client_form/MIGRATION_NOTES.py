"""
TODO: Alembic migration — add client form token fields to orders table.

Fields to add:
  client_form_token_hash        VARCHAR(64)   UNIQUE  NULLABLE  (SHA-256 hex digest)
  client_form_token_expires_at  TIMESTAMP     NULLABLE
  client_form_submitted_at      TIMESTAMP     NULLABLE

Note: column is named _hash (not _token) because we never store the raw token.

Steps:
  1. Run: flask db migrate -m "add client form token fields to orders"
  2. Review the generated migration file.
  3. Run: flask db upgrade
"""
