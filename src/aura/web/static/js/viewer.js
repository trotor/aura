/**
 * Aura — Karttakatselija (WMS, WFS, GeoJSON).
 *
 * Käyttö:
 *   initViewer({ type: "wms"|"wfs"|"geojson", url: "...", resourceId: "..." })
 */

/* global L */

function initViewer(config) {
    const map = L.map("viewer-map").setView([64.5, 26.0], 5);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "&copy; OpenStreetMap",
        maxZoom: 18,
    }).addTo(map);

    const statusEl = document.getElementById("viewer-status");
    function setStatus(msg) {
        if (statusEl) statusEl.textContent = msg;
    }

    if (config.type === "wms") {
        initWms(map, config, setStatus);
    } else if (config.type === "wfs") {
        initWfs(map, config, setStatus);
    } else if (config.type === "geojson") {
        initGeoJson(map, config, setStatus);
    }
}

// --- WMS ---

function initWms(map, config, setStatus) {
    setStatus("Ladataan WMS-tasoja...");

    const layerSelect = document.getElementById("layer-select");
    let currentLayer = null;

    fetch(`/api/wms/capabilities?url=${encodeURIComponent(config.url)}`)
        .then(r => r.json())
        .then(data => {
            if (data.error) {
                setStatus("Virhe: " + data.error);
                // Fallback: try showing the WMS directly
                addWmsLayer(map, config.url, "");
                return;
            }

            const layers = data.layers || [];
            if (!layers.length) {
                setStatus("Ei tasoja saatavilla.");
                return;
            }

            layerSelect.innerHTML = "";
            layerSelect.disabled = false;
            layers.forEach(l => {
                const opt = document.createElement("option");
                opt.value = l.name;
                opt.textContent = l.title || l.name;
                layerSelect.appendChild(opt);
            });

            layerSelect.addEventListener("change", () => {
                if (currentLayer) map.removeLayer(currentLayer);
                currentLayer = addWmsLayer(map, config.url, layerSelect.value);
                setStatus(`Taso: ${layerSelect.value}`);
            });

            // Activate first layer
            currentLayer = addWmsLayer(map, config.url, layers[0].name);
            setStatus(`${layers.length} tasoa ladattu.`);

            // Zoom to bbox if available
            if (data.bbox) {
                map.fitBounds([
                    [data.bbox[1], data.bbox[0]],
                    [data.bbox[3], data.bbox[2]],
                ]);
            }
        })
        .catch(e => {
            setStatus("Virhe ladattaessa: " + e.message);
            // Fallback: just add WMS layer
            addWmsLayer(map, config.url, "");
        });
}

function addWmsLayer(map, url, layerName) {
    // Clean URL: remove existing query params like service=, request=
    const baseUrl = url.split("?")[0];
    const layer = L.tileLayer.wms(baseUrl, {
        layers: layerName,
        format: "image/png",
        transparent: true,
        attribution: "WMS",
    });
    layer.addTo(map);
    return layer;
}

// --- WFS ---

function initWfs(map, config, setStatus) {
    setStatus("Ladataan WFS-featuretyyppejä...");

    const layerSelect = document.getElementById("layer-select");
    let currentLayer = null;

    fetch(`/api/wfs/capabilities?url=${encodeURIComponent(config.url)}`)
        .then(r => r.json())
        .then(data => {
            if (data.error) {
                setStatus("Virhe: " + data.error);
                return;
            }

            const types = data.feature_types || [];
            if (!types.length) {
                setStatus("Ei featuretyyppejä saatavilla.");
                return;
            }

            layerSelect.innerHTML = "";
            layerSelect.disabled = false;
            types.forEach(t => {
                const opt = document.createElement("option");
                opt.value = t.name;
                opt.textContent = t.title || t.name;
                layerSelect.appendChild(opt);
            });

            layerSelect.addEventListener("change", () => {
                loadWfsFeatures(map, config.url, layerSelect.value, setStatus, currentLayer)
                    .then(l => { currentLayer = l; });
            });

            // Load first type
            loadWfsFeatures(map, config.url, types[0].name, setStatus, null)
                .then(l => { currentLayer = l; });
        })
        .catch(e => setStatus("Virhe ladattaessa: " + e.message));
}

async function loadWfsFeatures(map, url, typeName, setStatus, prevLayer) {
    if (prevLayer) map.removeLayer(prevLayer);
    setStatus(`Ladataan: ${typeName}...`);

    try {
        const resp = await fetch(
            `/api/wfs/features?url=${encodeURIComponent(url)}&typeName=${encodeURIComponent(typeName)}&maxFeatures=500`
        );
        const data = await resp.json();

        if (data.error) {
            setStatus("Virhe: " + data.error);
            return null;
        }

        const geojson = data.geojson || data;
        const layer = L.geoJSON(geojson, {
            onEachFeature: function(feature, layer) {
                if (feature.properties) {
                    const props = feature.properties;
                    let html = '<table style="font-size:0.8rem">';
                    for (const [k, v] of Object.entries(props)) {
                        if (v != null && v !== "") {
                            html += `<tr><td><strong>${esc(k)}</strong></td><td>${esc(String(v))}</td></tr>`;
                        }
                    }
                    html += "</table>";
                    layer.bindPopup(html, { maxWidth: 400, maxHeight: 300 });
                }
            },
            style: {
                color: "#2171b5",
                weight: 2,
                fillOpacity: 0.3,
            },
            pointToLayer: function(feature, latlng) {
                return L.circleMarker(latlng, { radius: 6, color: "#2171b5", fillOpacity: 0.6 });
            },
        }).addTo(map);

        const count = geojson.features ? geojson.features.length : 0;
        setStatus(`${typeName}: ${count} featurea.`);

        if (count > 0) {
            map.fitBounds(layer.getBounds(), { padding: [20, 20] });
        }
        return layer;
    } catch(e) {
        setStatus("Virhe: " + e.message);
        return null;
    }
}

// --- GeoJSON ---

function initGeoJson(map, config, setStatus) {
    setStatus("Ladataan GeoJSON...");

    fetch(config.url)
        .then(r => {
            if (!r.ok) throw new Error(`HTTP ${r.status}`);
            return r.json();
        })
        .then(data => {
            const layer = L.geoJSON(data, {
                onEachFeature: function(feature, layer) {
                    if (feature.properties) {
                        const props = feature.properties;
                        let html = '<table style="font-size:0.8rem">';
                        for (const [k, v] of Object.entries(props)) {
                            if (v != null && v !== "") {
                                html += `<tr><td><strong>${esc(k)}</strong></td><td>${esc(String(v))}</td></tr>`;
                            }
                        }
                        html += "</table>";
                        layer.bindPopup(html, { maxWidth: 400, maxHeight: 300 });
                    }
                },
                style: {
                    color: "#2171b5",
                    weight: 2,
                    fillOpacity: 0.3,
                },
                pointToLayer: function(feature, latlng) {
                    return L.circleMarker(latlng, { radius: 6, color: "#2171b5", fillOpacity: 0.6 });
                },
            }).addTo(map);

            const count = data.features ? data.features.length : 1;
            setStatus(`${count} featurea ladattu.`);

            if (layer.getBounds().isValid()) {
                map.fitBounds(layer.getBounds(), { padding: [20, 20] });
            }
        })
        .catch(e => setStatus("Virhe: " + e.message));
}

// --- Helpers ---

function esc(s) {
    const d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
}
