-- Sotkanetin omat aluetunnukset kuntataulun riveille.
--
-- Sotkanet ei kysele kuntakoodilla vaan omalla aluetunnuksellaan:
-- Kuopio on kuntakoodiltaan 297 mutta Sotkanetissa alue 161. Ilman
-- tätä siltaa Sotkanetin 3 772 indikaattoria ovat kuntatasolla
-- saavuttamattomia — kysyjän on ensin haettava /rest/1.1/regions
-- itse ja etsittävä kunta nimellä.
--
-- Kaikki kolme tasoa mapattiin 16.8.2026 täydellisesti: 308/308
-- kuntaa, 19/19 maakuntaa, 23/23 hyvinvointialuetta. Maakunta ja
-- hyvinvointialue toistuvat kunnittain, koska taulussa ei ole
-- erillisiä alue-rivejä; toisto on halvempi kuin uusi taulu.
--
-- Nullable kunnes populoitu (populator: municipalities).

ALTER TABLE ref_municipalities ADD COLUMN sotkanet_id INTEGER;
ALTER TABLE ref_municipalities ADD COLUMN sotkanet_region_id INTEGER;
ALTER TABLE ref_municipalities ADD COLUMN sotkanet_wellbeing_area_id INTEGER;

CREATE INDEX IF NOT EXISTS idx_ref_municipalities_sotkanet
    ON ref_municipalities(sotkanet_id);
