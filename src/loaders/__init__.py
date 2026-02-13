"""Data loading: templates, Search Console, Clearscope, case studies."""

from src.loaders.templates import (
    load_keywords,
    load_headers,
    load_questions,
    extract_tech_from_url,
)
from src.loaders.search_console import pull_sc_queries, load_sc_queries
from src.loaders.clearscope import load_clearscope_terms, check_term_coverage
from src.loaders.case_studies import get_case_studies, scrape_case_studies

__all__ = [
    "load_keywords",
    "load_headers",
    "load_questions",
    "extract_tech_from_url",
    "pull_sc_queries",
    "load_sc_queries",
    "load_clearscope_terms",
    "check_term_coverage",
    "get_case_studies",
    "scrape_case_studies",
]
