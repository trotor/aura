# Aura – kysy Suomen avoimelta datalta

Aura kokoaa Suomen avoimen datan yhteen hakemistoon ja hakee vastaukset suoraan julkaisijan rajapinnasta, lähde ja lisenssi mukana. Käytä sitä selaimella osoitteessa **[aura.futuai.fi](https://aura.futuai.fi)** tai liitä se tekoälyavustajaasi.

[English](https://github.com/trotor/aura/blob/main/README.en.md) | [Svenska](https://github.com/trotor/aura/blob/main/README.sv.md)

![Auran etusivu](assets/img/etusivu.png)

**13 300+ aineistoa, 32 000+ resurssia, 46 lähdettä, noin 400 julkaisijaa.**

---

## Liitä tekoälyavustajaan

```bash
claude mcp add --transport http aura https://aura.futuai.fi/mcp
```

Ei tunnuksia, ei asennusta. Muut asiakkaat: [MCP-käyttöönotto](MCP_SETUP.md).

![Claude vastaa Auran avulla](assets/img/keskustelu.png)

---

## Mitä voit kysyä

| Kysymys | Vastaus (8.10.2026) |
|---|---|
| Mikä on Kuopion työttömyysaste? | 12,4 % vuonna 2024 (Tilastokeskus). TEM:n työnvälitystilasto antaa 11,1 %, ja vastaus kertoo eron syyn. |
| Paljonko Kuopio on kasvanut kymmenessä vuodessa? | 116 921 → 126 572 asukasta, +8,3 % |
| Hur hög är arbetslösheten i Vasa? | 8,8 % vuonna 2024 |
| air quality Helsinki | Ilmatieteen laitoksen ilmanlaatuennuste ja HSY:n ilmanlaatuindeksit |

---

## Miten se toimii

![Auran arkkitehtuuri](assets/img/arkkitehtuuri.svg)

Aura kerää lähteistä metatiedot ja pitää ne haettavana hakemistona. Tekoälyagentti etsii aineiston (`find_data`), selvittää mitä siinä on (`inspect_dataset`) ja hakee rivit suoraan lähteestä (`query_source`). Jokainen vastaus on strukturoitu ja kertoo lähteen, kyselyn URL:n ja lisenssin.

---

## Sama tekniikka omalle datalle

Aura ei ole sidottu avoimeen dataan. Sama rakenne – keräin lähdettä kohden, yksi metatietohakemisto, suomea ymmärtävä haku ja MCP-työkalut, jotka kertovat lähteen – toimii myös organisaation omille tietokannoille, rajapinnoille ja paikkatietopalveluille. Koodi ja ohjeet uuden keräimen tekemiseen ovat [GitHubissa](https://github.com/trotor/aura).

---

## Dokumentaatio

- [README](https://github.com/trotor/aura#readme): esittely, esimerkit ja Aura Pro
- [Tekninen referenssi](REFERENCE.md): asennus, työkalut, komentorivi, rajausaineistot
- [Datasettikatalogi](CATALOG.md) ja [datalähteet](SOURCES.md)
- [Organisaatiot](organisaatiot.md) ja [kunnat](kunnat.md)
- [Dataformaatit](formats.md)
- [Mitä uutta](WHATSNEW.md)

## Tekijä

Auran on rakentanut Tero Rönkkö ([tero@futuai.fi](mailto:tero@futuai.fi)). Projektin on mahdollistanut Futuai Oy, joka tarjoaa julkisen palvelun osoitteessa [aura.futuai.fi](https://aura.futuai.fi).

## Lähdekoodi

[GitHub: trotor/aura](https://github.com/trotor/aura) | [CONTRIBUTING](https://github.com/trotor/aura/blob/main/CONTRIBUTING.md) | [MIT-lisenssi](https://github.com/trotor/aura/blob/main/LICENSE)
