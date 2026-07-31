"""Audit feature module.

Purpose: Persist significant system actions.
Responsibilities: AuditLog model and repository.
Dependencies: auth, shared.database.
Extension points: Action catalogs, retention jobs.
"""

from app.audit.models import AuditLog
from app.audit.repository import AuditRepository, SqlAlchemyAuditRepository

__all__ = ["AuditLog", "AuditRepository", "SqlAlchemyAuditRepository"]
