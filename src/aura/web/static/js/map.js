/* Aura — Leaflet-kartan logiikka */

(function() {
    "use strict";

    var map = L.map("map").setView([64.5, 26.0], 5);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: '&copy; <a href="https://openstreetmap.org">OpenStreetMap</a>',
        maxZoom: 18,
    }).addTo(map);

    var geojsonLayer = null;
    var datasetCounts = {};

    function getColor(count) {
        if (count === 0) return "#f0f0f0";
        if (count <= 5) return "#c6dbef";
        if (count <= 20) return "#6baed6";
        if (count <= 50) return "#2171b5";
        if (count <= 100) return "#08519c";
        return "#08306b";
    }

    function style(feature) {
        var name = feature.properties.name;
        var count = datasetCounts[name] || 0;
        return {
            fillColor: getColor(count),
            weight: 1,
            opacity: 0.7,
            color: "#666",
            fillOpacity: 0.6
        };
    }

    function onEachFeature(feature, layer) {
        var name = feature.properties.name;
        var count = datasetCounts[name] || 0;
        layer.bindTooltip(name + ": " + count + " datasettia");

        layer.on("click", function() {
            document.getElementById("sidebar-title").textContent = name;
            var content = document.getElementById("sidebar-content");
            content.innerHTML = '<p aria-busy="true">Haetaan...</p>';

            fetch("/search/results?q=&source=&fmt=&organization=&page=1&q=" + encodeURIComponent(name))
                .then(function(r) { return r.text(); })
                .then(function(html) {
                    content.innerHTML = html || "<p>Ei datasetteja.</p>";
                })
                .catch(function() {
                    content.innerHTML = "<p>Haku epÃ¤onnistui.</p>";
                });
        });
    }

    // Lataa data
    Promise.all([
        fetch("/api/geo/municipalities").then(function(r) { return r.json(); }),
        fetch("/api/geo/dataset-counts").then(function(r) { return r.json(); })
    ]).then(function(results) {
        var geojson = results[0];
        datasetCounts = results[1].counts || {};

        geojsonLayer = L.geoJSON(geojson, {
            style: style,
            onEachFeature: onEachFeature
        }).addTo(map);

        if (geojsonLayer.getBounds().isValid()) {
            map.fitBounds(geojsonLayer.getBounds());
        }
    }).catch(function(err) {
        console.error("Karttadatan lataus epÃ¤onnistui:", err);
    });

    // Legenda
    var legend = L.control({ position: "bottomright" });
    legend.onAdd = function() {
        var div = L.DomUtil.create("div", "legend");
        div.style.background = "white";
        div.style.padding = "8px";
        div.style.borderRadius = "4px";
        div.style.fontSize = "12px";
        div.style.lineHeight = "1.8";
        var grades = [0, 1, 5, 20, 50, 100];
        var labels = ["0", "1–5", "6–20", "21–50", "51–100", "100+"];
        div.innerHTML = "<strong>Datasetteja</strong><br>";
        for (var i = 0; i < grades.length; i++) {
            div.innerHTML +=
                '<span style="display:inline-block;width:14px;height:14px;background:' +
                getColor(grades[i] || 0.5) +
                ';margin-right:4px;vertical-align:middle;border-radius:2px"></span> ' +
                labels[i] + "<br>";
        }
        return div;
    };
    legend.addTo(map);
})();
