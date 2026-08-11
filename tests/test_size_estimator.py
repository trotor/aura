"""Testit size_estimator-moduulille."""


from aura.size_estimator import (
    DEFAULT_SIZE_ESTIMATE,
    FORMAT_SIZE_ESTIMATES,
    estimate_dataset_size,
    format_size,
    parse_file_size,
)

# -- parse_file_size ----------------------------------------------------------


class TestParseFileSize:
    def test_empty_string(self) -> None:
        assert parse_file_size("") == 0

    def test_plain_number(self) -> None:
        assert parse_file_size("1000") == 1000

    def test_decimal_truncated(self) -> None:
        assert parse_file_size("1.5") == 1

    def test_kb(self) -> None:
        assert parse_file_size("1 KB") == 1024

    def test_mb(self) -> None:
        assert parse_file_size("1 MB") == 1_048_576

    def test_gb_decimal(self) -> None:
        assert parse_file_size("2.5 GB") == 2_684_354_560

    def test_tb(self) -> None:
        assert parse_file_size("1 TB") == 1_099_511_627_776

    def test_bytes_unit(self) -> None:
        assert parse_file_size("1024 BYTES") == 1024

    def test_unknown_string(self) -> None:
        assert parse_file_size("unknown") == 0

    def test_whitespace_stripped(self) -> None:
        assert parse_file_size("  500 KB  ") == 512_000


# -- estimate_dataset_size ----------------------------------------------------


class TestEstimateDatasetSize:
    def test_empty_list(self) -> None:
        assert estimate_dataset_size([]) == 0

    def test_known_file_size(self) -> None:
        resources = [{"file_size": "2 MB", "format": "CSV"}]
        assert estimate_dataset_size(resources) == 2_097_152

    def test_no_size_known_format(self) -> None:
        resources = [{"format": "CSV"}]
        assert estimate_dataset_size(resources) == FORMAT_SIZE_ESTIMATES["CSV"]

    def test_no_size_unknown_format(self) -> None:
        resources = [{"format": "FOOBAR"}]
        assert estimate_dataset_size(resources) == DEFAULT_SIZE_ESTIMATE

    def test_multiple_resources_summed(self) -> None:
        resources = [
            {"file_size": "1 KB"},
            {"file_size": "2 KB"},
        ]
        assert estimate_dataset_size(resources) == 1024 + 2048


# -- format_size --------------------------------------------------------------


class TestFormatSize:
    def test_zero(self) -> None:
        assert format_size(0) == "–"

    def test_bytes(self) -> None:
        assert format_size(500) == "500 B"

    def test_kb(self) -> None:
        assert format_size(1024) == "1 KB"

    def test_mb(self) -> None:
        assert format_size(1_048_576) == "1.0 MB"

    def test_gb(self) -> None:
        assert format_size(1_073_741_824) == "1.0 GB"

    def test_tb(self) -> None:
        assert format_size(1_099_511_627_776) == "1.0 TB"
