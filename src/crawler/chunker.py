"""Document chunking strategy."""

import re

import xxhash

from ..shared.config import settings
from ..shared.models import DocumentChunk, DocumentMetadata


class DocumentChunker:
    """Split documents into semantic chunks for vector storage."""

    def __init__(
        self,
        max_chunk_tokens: int = settings.max_chunk_tokens,
        overlap_tokens: int = settings.chunk_overlap_tokens,
    ):
        self.max_chunk_tokens = max_chunk_tokens
        self.overlap_tokens = overlap_tokens
        self.heading_pattern = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

    def chunk(self, content: str, metadata: DocumentMetadata) -> list[DocumentChunk]:
        """Split markdown content into chunks.

        Strategy:
        1. Split on H2 boundaries (major sections)
        2. If section > max_tokens, split on paragraphs
        3. Preserve heading context for each chunk
        """
        document_id = xxhash.xxh64(metadata.url.encode()).hexdigest()
        sections = self._split_by_headings(content)

        chunks = []
        chunk_index = 0

        for heading_context, section_text in sections:
            section_chunks = self._chunk_section(section_text, heading_context)

            for chunk_text in section_chunks:
                if not chunk_text.strip():
                    continue

                chunk_id = f"{document_id}_{chunk_index}"
                chunk = DocumentChunk(
                    id=chunk_id,
                    document_id=document_id,
                    content=chunk_text,
                    chunk_index=chunk_index,
                    heading_context=heading_context,
                    metadata=metadata,
                )
                chunks.append(chunk)
                chunk_index += 1

        return chunks

    def _split_by_headings(self, content: str) -> list[tuple[list[str], str]]:
        """Split content by heading hierarchy.

        Returns list of (heading_path, section_text) tuples.
        """
        lines = content.split("\n")
        sections: list[tuple[list[str], str]] = []
        current_headings: list[str] = []
        current_section: list[str] = []

        for line in lines:
            heading_match = self.heading_pattern.match(line)

            if heading_match:
                # Save previous section if it has content
                if current_section:
                    section_text = "\n".join(current_section).strip()
                    if section_text:
                        sections.append((list(current_headings), section_text))
                    current_section = []

                # Update heading context
                level = len(heading_match.group(1))  # Number of #
                heading_text = heading_match.group(2).strip()

                # Trim headings to current level
                current_headings = current_headings[: level - 1]
                current_headings.append(heading_text)

                # Include heading in section
                current_section.append(line)
            else:
                current_section.append(line)

        # Don't forget the last section
        if current_section:
            section_text = "\n".join(current_section).strip()
            if section_text:
                sections.append((list(current_headings), section_text))

        return sections

    def _chunk_section(self, text: str, heading_context: list[str]) -> list[str]:
        """Split a section into chunks if it's too large."""
        tokens = self._estimate_tokens(text)

        if tokens <= self.max_chunk_tokens:
            return [text]

        # Split by paragraphs
        paragraphs = text.split("\n\n")
        chunks = []
        current_chunk: list[str] = []
        current_tokens = 0

        for para in paragraphs:
            para_tokens = self._estimate_tokens(para)

            if current_tokens + para_tokens > self.max_chunk_tokens:
                if current_chunk:
                    chunks.append("\n\n".join(current_chunk))
                current_chunk = [para]
                current_tokens = para_tokens
            else:
                current_chunk.append(para)
                current_tokens += para_tokens

        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        return chunks

    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimation (words * 1.3)."""
        return int(len(text.split()) * 1.3)
