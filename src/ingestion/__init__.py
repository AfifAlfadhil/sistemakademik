"""Ingestion module for NLP pipeline."""

from .parser import parse_legal_pdf_to_markdown, extract_document_metadata
from .chunker import chunk_markdown
from .metadata_tagger import enrich_chunk_metadata

__all__ = [
    "parse_legal_pdf_to_markdown",
    "extract_document_metadata",
    "chunk_markdown",
    "enrich_chunk_metadata"
]
