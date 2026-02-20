"""Tietomallit avoindata.fi:n dataseteille."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from aura.size_estimator import estimate_dataset_size


class Resource(BaseModel):
    """Yksittäinen dataresurssi (tiedosto tai rajapinta)."""

    id: str
    name: str
    name_fi: str = ""
    name_en: str = ""
    description: str = ""
    description_fi: str = ""
    description_en: str = ""
    format: str = ""
    url: str = ""
    file_size: str = ""
    last_modified: str | None = None


class Organization(BaseModel):
    """Datan julkaisija."""

    id: str
    name: str
    title: str = ""
    title_fi: str = ""
    title_en: str = ""
    description: str = ""
    image_url: str = ""
    homepage: str = ""


class Dataset(BaseModel):
    """Yksittäinen datasetti metadatoineen."""

    id: str
    name: str
    title: str = ""
    title_fi: str = ""
    title_en: str = ""
    title_sv: str = ""
    notes: str = ""
    notes_fi: str = ""
    notes_en: str = ""
    notes_sv: str = ""
    license_id: str = ""
    license_title: str = ""
    organization_id: str = ""
    organization_name: str = ""
    organization_title: str = ""
    metadata_created: str = ""
    metadata_modified: str = ""
    keywords_fi: list[str] = Field(default_factory=list)
    keywords_en: list[str] = Field(default_factory=list)
    geographical_coverage: list[str] = Field(default_factory=list)
    update_frequency: str = ""
    collection_type: str = ""
    num_resources: int = 0
    resources: list[Resource] = Field(default_factory=list)
    source: str = "avoindata.fi"
    estimated_size_bytes: int = 0

    @classmethod
    def from_ckan(cls, data: dict[str, Any], source: str = "avoindata.fi") -> Dataset:
        """Luo Dataset CKAN API:n vastauksen pohjalta."""
        title_translated = data.get("title_translated", {}) or {}
        notes_translated = data.get("notes_translated", {}) or {}
        keywords = data.get("keywords", {}) or {}
        org = data.get("organization", {}) or {}
        update_freq_raw = data.get("update_frequency", {}) or {}
        if isinstance(update_freq_raw, dict):
            val = update_freq_raw.get("fi", "")
            update_freq = ", ".join(val) if isinstance(val, list) else str(val)
        elif isinstance(update_freq_raw, list):
            update_freq = ", ".join(str(v) for v in update_freq_raw)
        else:
            update_freq = str(update_freq_raw)

        resources = []
        for r in data.get("resources", []):
            name_tr = r.get("name_translated", {}) or {}
            desc_tr = r.get("description_translated", {}) or {}
            resources.append(
                Resource(
                    id=r.get("id", ""),
                    name=r.get("name", ""),
                    name_fi=name_tr.get("fi", ""),
                    name_en=name_tr.get("en", ""),
                    description=r.get("description", ""),
                    description_fi=desc_tr.get("fi", ""),
                    description_en=desc_tr.get("en", ""),
                    format=r.get("format", ""),
                    url=r.get("url", ""),
                    file_size=r.get("file_size", "") or "",
                    last_modified=r.get("last_modified"),
                )
            )

        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            title=data.get("title", ""),
            title_fi=title_translated.get("fi", ""),
            title_en=title_translated.get("en", ""),
            title_sv=title_translated.get("sv", ""),
            notes=data.get("notes", ""),
            notes_fi=notes_translated.get("fi", ""),
            notes_en=notes_translated.get("en", ""),
            notes_sv=notes_translated.get("sv", ""),
            license_id=data.get("license_id", "") or "",
            license_title=data.get("license_title", "") or "",
            organization_id=org.get("id", ""),
            organization_name=org.get("name", ""),
            organization_title=org.get("title", ""),
            metadata_created=data.get("metadata_created", ""),
            metadata_modified=data.get("metadata_modified", ""),
            keywords_fi=keywords.get("fi", []),
            keywords_en=keywords.get("en", []),
            geographical_coverage=data.get("geographical_coverage", []) or [],
            update_frequency=update_freq,
            collection_type=data.get("collection_type", ""),
            num_resources=data.get("num_resources", 0),
            resources=resources,
            source=source,
            estimated_size_bytes=cls._estimate_ckan_size(data, resources),
        )

    @staticmethod
    def _estimate_ckan_size(data: dict[str, Any], resources: list[Resource]) -> int:
        """Arvioi CKAN-datasetin koko resurssien perusteella."""
        resource_dicts = [
            {"file_size": r.file_size, "format": r.format}
            for r in resources
        ]
        return estimate_dataset_size(resource_dicts)
