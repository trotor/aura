"""Testit spatial_probe-moduulille."""

from aura.spatial_probe import (
    FINLAND_AREA_KM2,
    FINLAND_BBOX,
    GTK_WFS_TARGETS,
    METSAKESKUS_WCS_TARGETS,
    METSAKESKUS_WFS_TARGETS,
    SAMPLE_BBOXES,
    ProbeResult,
    ProbeTarget,
    SampleResult,
    _bbox_area_km2,
    _format_bytes,
    format_probe_report,
    get_targets,
)


class TestConstants:
    """Vakioiden oikeellisuus."""

    def test_finland_bbox_valid(self):
        """Suomen bbox on järkevä."""
        lon_min, lat_min, lon_max, lat_max = FINLAND_BBOX
        assert lon_min < lon_max
        assert lat_min < lat_max
        assert 19 < lon_min < 20
        assert 59 < lat_min < 60
        assert 31 < lon_max < 32
        assert 70 < lat_max < 71

    def test_finland_area(self):
        """Suomen pinta-ala on oikein."""
        assert 330_000 < FINLAND_AREA_KM2 < 340_000

    def test_sample_bboxes_valid(self):
        """Otosalueet ovat Suomessa ja järkeväkokoisia."""
        for name, bbox in SAMPLE_BBOXES:
            lon_min, lat_min, lon_max, lat_max = bbox
            assert lon_min < lon_max, f"{name}: lon_min >= lon_max"
            assert lat_min < lat_max, f"{name}: lat_min >= lat_max"
            # Alue on Suomessa
            assert 19 < lon_min < 32, f"{name}: lon_min ei Suomessa"
            assert 59 < lat_min < 71, f"{name}: lat_min ei Suomessa"
            # Koko on ~10×10 km (0.1-0.2 astetta)
            assert 0.05 < (lon_max - lon_min) < 0.3
            assert 0.05 < (lat_max - lat_min) < 0.3

    def test_five_sample_areas(self):
        """Otosalueita on 5."""
        assert len(SAMPLE_BBOXES) == 5


class TestBboxArea:
    """bbox-pinta-alalaskenta."""

    def test_area_positive(self):
        """Pinta-ala on positiivinen."""
        area = _bbox_area_km2((25.0, 60.0, 25.1, 60.1))
        assert area > 0

    def test_area_roughly_correct(self):
        """Helsingin alueen pinta-ala on ~100 km² luokkaa."""
        _, bbox = SAMPLE_BBOXES[0]  # Helsinki
        area = _bbox_area_km2(bbox)
        assert 30 < area < 300  # Karkea tarkistus


class TestFormatBytes:
    """Tavumuotoilu."""

    def test_bytes(self):
        assert _format_bytes(500) == "500 B"

    def test_kilobytes(self):
        assert "KB" in _format_bytes(5000)

    def test_megabytes(self):
        assert "MB" in _format_bytes(5 * 1024**2)

    def test_gigabytes(self):
        assert "GB" in _format_bytes(5 * 1024**3)


class TestDataclasses:
    """Tietorakenteiden luonti."""

    def test_probe_target_defaults(self):
        """ProbeTarget-oletus-arvot toimivat."""
        t = ProbeTarget(
            dataset_id="test",
            endpoint_url="http://example.com/wfs",
            service_type="WFS",
        )
        assert t.srs == "EPSG:4326"
        assert t.max_features == 100
        assert t.current_estimated_bytes == 0

    def test_probe_result_defaults(self):
        """ProbeResult-oletus-arvot toimivat."""
        r = ProbeResult(
            dataset_id="test",
            endpoint_url="http://example.com/wfs",
        )
        assert r.total_feature_count is None
        assert r.samples == []
        assert r.error == ""

    def test_sample_result(self):
        """SampleResult luodaan oikein."""
        s = SampleResult(area_name="Helsinki", feature_count=42, response_bytes=1024)
        assert s.area_name == "Helsinki"
        assert s.feature_count == 42


class TestGetTargets:
    """Kohteiden haku lähteen perusteella."""

    def test_all_targets(self):
        """'all' palauttaa kaikki kohteet."""
        targets = get_targets("all")
        assert len(targets) > 0
        ids = [t.dataset_id for t in targets]
        assert any("metsakeskus" in i for i in ids)
        assert any("gtk" in i for i in ids)

    def test_metsakeskus_targets(self):
        """'metsakeskus' palauttaa vain Metsäkeskuksen kohteet."""
        targets = get_targets("metsakeskus")
        for t in targets:
            assert "metsakeskus" in t.dataset_id

    def test_gtk_targets(self):
        """'gtk' palauttaa vain GTK:n kohteet."""
        targets = get_targets("gtk")
        for t in targets:
            assert "gtk" in t.dataset_id

    def test_target_lists_nonempty(self):
        """Kaikki kohdelistat sisältävät kohteita."""
        assert len(METSAKESKUS_WFS_TARGETS) > 0
        assert len(METSAKESKUS_WCS_TARGETS) > 0
        assert len(GTK_WFS_TARGETS) > 0


class TestFormatReport:
    """Raportin muotoilu."""

    def test_empty_results(self):
        """Tyhjä tuloslista palauttaa viestin."""
        report = format_probe_report([])
        assert "Ei mittaustuloksia" in report

    def test_report_with_results(self):
        """Raportti sisältää taulukon otsikot."""
        results = [
            ProbeResult(
                dataset_id="metsakeskus-stand",
                endpoint_url="http://example.com/wfs",
                total_feature_count=1000,
                sample_bytes=50000,
                bytes_per_feature=50.0,
                extrapolated_size_bytes=50000000,
                current_estimated_bytes=50 * 1024**3,
            ),
        ]
        report = format_probe_report(results)
        assert "metsakeskus-stand" in report
        assert "Datasetti" in report
        assert "Featureja" in report

    def test_report_with_error(self):
        """Virheellinen tulos näkyy raportissa."""
        results = [
            ProbeResult(
                dataset_id="gtk-maapera",
                endpoint_url="http://example.com/wfs",
                error="Timeout",
                current_estimated_bytes=3 * 1024**3,
            ),
        ]
        report = format_probe_report(results)
        assert "gtk-maapera" in report
        assert "VIRHE" in report
