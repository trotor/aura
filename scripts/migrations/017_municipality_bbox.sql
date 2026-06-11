-- Kuntien bbox (EPSG:3067) aluerajauksiin — populoidaan kuntajako_1000k.gpkg:sta
-- (populator: municipality_bbox). Nullable kunnes populoitu.

ALTER TABLE ref_municipalities ADD COLUMN min_x REAL;
ALTER TABLE ref_municipalities ADD COLUMN min_y REAL;
ALTER TABLE ref_municipalities ADD COLUMN max_x REAL;
ALTER TABLE ref_municipalities ADD COLUMN max_y REAL;
