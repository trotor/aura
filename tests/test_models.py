"""Testit tietomalleille."""

from aura.models import Dataset


def test_dataset_from_ckan_minimal():
    """Testi minimaalisella CKAN-datalla."""
    raw = {
        "id": "test-id-123",
        "name": "test-dataset",
        "title": "Test Dataset",
    }
    dataset = Dataset.from_ckan(raw)
    assert dataset.id == "test-id-123"
    assert dataset.name == "test-dataset"
    assert dataset.title == "Test Dataset"
    assert dataset.source == "avoindata.fi"


def test_dataset_from_ckan_full():
    """Testi täydellä CKAN-datalla."""
    raw = {
        "id": "abc-123",
        "name": "helsinki-vaesto",
        "title": "Helsingin väestö",
        "title_translated": {"fi": "Helsingin väestö", "en": "Helsinki population", "sv": ""},
        "notes": "Väestötiedot",
        "notes_translated": {"fi": "Väestötiedot Helsingistä", "en": "Population data"},
        "license_id": "cc-by-4.0",
        "license_title": "CC BY 4.0",
        "organization": {
            "id": "org-1",
            "name": "helsinki",
            "title": "Helsingin kaupunki",
        },
        "metadata_created": "2024-01-01T00:00:00",
        "metadata_modified": "2024-06-01T00:00:00",
        "keywords": {"fi": ["väestö", "helsinki"], "en": ["population"]},
        "geographical_coverage": ["Helsinki"],
        "update_frequency": {"fi": "vuosittain"},
        "collection_type": "Open Data",
        "num_resources": 1,
        "resources": [
            {
                "id": "res-1",
                "name": "vaesto.csv",
                "name_translated": {"fi": "Väestödata", "en": "Population data"},
                "description": "",
                "description_translated": {"fi": "", "en": ""},
                "format": "CSV",
                "url": "https://example.com/vaesto.csv",
                "file_size": "1024",
                "last_modified": "2024-06-01",
            }
        ],
    }
    dataset = Dataset.from_ckan(raw)
    assert dataset.title_fi == "Helsingin väestö"
    assert dataset.title_en == "Helsinki population"
    assert dataset.organization_title == "Helsingin kaupunki"
    assert len(dataset.resources) == 1
    assert dataset.resources[0].format == "CSV"
    assert dataset.keywords_fi == ["väestö", "helsinki"]
