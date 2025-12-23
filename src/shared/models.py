"""Pydantic models for Databricks documentation data."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class DocumentCategory(str, Enum):
    """Main documentation categories from Databricks docs."""

    ADMIN = "admin"
    AI_BI = "ai-bi"
    AI_GATEWAY = "ai-gateway"
    COMPUTE = "compute"
    CONNECT = "connect"
    DATA_GOVERNANCE = "data-governance"
    DELTA = "delta"
    DEV_TOOLS = "dev-tools"
    DASHBOARDS = "dashboards"
    DATA_ENGINEERING = "data-engineering"
    DELTA_SHARING = "delta-sharing"
    DBFS = "dbfs"
    CATALOGS = "catalogs"
    DATA_QUALITY = "data-quality-monitoring"
    MACHINE_LEARNING = "machine-learning"
    GENERATIVE_AI = "generative-ai"
    SQL = "sql"
    GETTING_STARTED = "getting-started"
    LAKEHOUSE = "lakehouse"
    NOTEBOOKS = "notebooks"
    REPOS = "repos"
    WORKFLOWS = "workflows"
    PARTNERS = "partners"
    RELEASE_NOTES = "release-notes"
    RESOURCES = "resources"
    OTHER = "other"


class DocumentMetadata(BaseModel):
    """Metadata for a documentation page."""

    url: str = Field(description="Full URL of the documentation page")
    path: str = Field(description="URL path (e.g., /aws/en/compute/clusters)")
    title: str = Field(description="Page title extracted from H1 or meta")
    category: str = Field(description="Primary category")
    subcategory: Optional[str] = Field(default=None, description="Subcategory if applicable")
    breadcrumb: list[str] = Field(default_factory=list, description="Navigation breadcrumb")
    last_modified: Optional[datetime] = Field(default=None, description="Last modification date")
    content_hash: str = Field(default="", description="Hash of content for change detection")


class DocumentChunk(BaseModel):
    """A chunk of documentation content."""

    id: str = Field(description="Unique chunk ID (url_hash + chunk_index)")
    document_id: str = Field(description="Parent document URL hash")
    content: str = Field(description="Chunk text content (markdown)")
    chunk_index: int = Field(description="Position in document (0-indexed)")
    heading_context: list[str] = Field(
        default_factory=list, description="Heading hierarchy for context"
    )
    metadata: DocumentMetadata


class Section(BaseModel):
    """Section representation for list-sections tool."""

    title: str = Field(description="Section title")
    path: str = Field(description="URL path for this section")
    use_cases: list[str] = Field(description="Common use cases for this section")
    category: str
    subcategory: Optional[str] = None
    child_count: int = Field(default=0, description="Number of child pages")


class SectionList(BaseModel):
    """Response model for list-sections tool."""

    sections: list[Section]
    total_count: int
    categories: list[str]


class DocumentationContent(BaseModel):
    """Response model for get-documentation tool."""

    path: str
    title: str
    content: str = Field(description="Full markdown content")
    breadcrumb: list[str]
    related_paths: list[str] = Field(default_factory=list)
