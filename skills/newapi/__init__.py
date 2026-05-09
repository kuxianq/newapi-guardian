"""NewAPI 运维 Skill"""
from .docs import DOC_TOPICS, NEWAPI_DOCS_URL, NEWAPI_GITHUB_URL, get_newapi_docs
from .schema import DATABASE_SCHEMA, SQL_TEMPLATES

__all__ = [
    "DATABASE_SCHEMA",
    "SQL_TEMPLATES",
    "DOC_TOPICS",
    "NEWAPI_DOCS_URL",
    "NEWAPI_GITHUB_URL",
    "get_newapi_docs",
]
