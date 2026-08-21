-- Kielimallin ehdottamat käyttötapaukset omaan kenttäänsä.
--
-- use_case on ainoa kenttä joka ei ole johdettavissa lähteestä. Generoitu
-- sisältö muuttuu katalogissa faktaksi seuraavalle lukijalle, ja
-- source_type='ai_analysis' ei näy siinä kohdassa jossa arvo luetaan.
-- Kentän nimi näkyy.
--
-- Rivejä ei poisteta: sisältö säilyy, vain sen nimi muuttuu todeksi.

UPDATE enrichments
   SET field = 'use_case_suggested'
 WHERE field = 'use_case'
   AND source_type = 'ai_analysis';
