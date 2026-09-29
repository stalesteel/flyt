# Flyt

Privat kart for bruk på Øyeren.
Ligger på **GitHub Pages** og publiseres til <https://flyt.klommestein.no> automatisk
når endringer pushes til `main`.

## Adresser

| Adresse | Hva det er |
|---|---|
| `/` | Kartet |
| `/lab` | Eksperimentell versjon uten ArcGIS Online og uten innlogging, se [Lab](#lab) |

## Gjenstår å rydde

Sjekklistene er flyttet ut i en egen app på <https://husk.klommestein.no>, og knappene
i kartmenyen peker dit. Det eneste som henger igjen er **ArcGIS-tabellen
`SjekklisteFlyt`**, som ikke brukes lenger. Denne slettingen kan ikke angres. Innholdet er
trygt uansett: alle 22 punktene ligger både i Husk og i `DESIGN.md` i husk-repoet.
Vent gjerne til Husk er prøvd noen ganger i praksis.

## Tilgangssperre

Hovedkartet ligger bak en enkel innlogging (ikke `/lab`): brukernavn **Tone**, passord **Berit**.
Store og små bokstaver spiller ingen rolle i brukernavnet; passordet må skrives nøyaktig.
Innloggingen huskes i 90 dager i nettleseren.

### Hva dette er og ikke er

Dette er en **dørmatte, ikke en lås**. GitHub Pages serverer bare statiske filer, så det
finnes ingen server å gjøre sjekken på — alt skjer i nettleseren. I tillegg er repoet
offentlig, så hvem som helst kan lese `index.html` og resten av kildekoden direkte på
GitHub uansett hva innloggingssiden sier. Kartdataene ligger i ArcGIS, men tjenestene
er delt offentlig og kan leses av den som kjenner URL-en.

Sperren holder tilfeldige besøkende ute. Den stopper ingen som åpner utviklerverktøy
eller finner repoet. Legg derfor **aldri noe sensitivt** i disse filene.

Vil du ha ekte beskyttelse, må siden flyttes til en server som kan kjøre kode —
for eksempel ProISP-webhotellet, der `.htaccess` eller PHP kan gjøre jobben.

### Endre brukernavn eller passord

Alt ligger i [`auth.js`](auth.js). Passordet lagres som en saltet SHA-256-hash, ikke i
klartekst, slik at det ikke står lesbart i et offentlig repo.

Nytt passord regnes ut slik (bytt `NyttPassord`):

```bash
python -c "import hashlib; print(hashlib.sha256(('flyt-oyeren-2026:' + 'NyttPassord').encode()).hexdigest())"
```

Lim resultatet inn i `PASSWORD_HASH` i `auth.js`. Brukernavnet står i `USERNAME` og
skal skrives med små bokstaver. Endrer du `SALT`, må hashen regnes ut på nytt.

Alle som allerede er innlogget forblir innlogget til de 90 dagene løper ut. Vil du kaste
alle ut umiddelbart, bytt også `STORAGE_KEY` i `auth.js`.

## Kartet

Kartet bruker ArcGIS Maps SDK for JavaScript og et webkart i ArcGIS Online
(`d275f3cbd6be4f6f9a3196e1ecd3d202`), i UTM33 / EPSG:25833.

Data lagres i disse tjenestene:

| Lag | Tjeneste |
|---|---|
| Bilder | `BilderInnsjo/FeatureServer/0` |
| Interessepunkt | `POI_Innsjo/FeatureServer/0` |
| Led | `LedOyeren/FeatureServer/1` |
| Samferdsel | `GeomapSamferdsel/MapServer` (Geodata) |

Merk at bilde- og interessepunktlagene tar imot innsending fra hvem som helst som kommer
gjennom innloggingen, uten videre autentisering mot ArcGIS.

## Lab

`/lab` er en eksperimentell versjon som skal kunne deles åpent med andre båtfolk på
Øyeren. Hovedkartet på `/` er urørt og virker som før.

Forskjeller fra hovedkartet:

- **Ingen innlogging, bilder, sjekklister eller redigering av interessepunkter.**
- **Ingen avhengighet til ArcGIS Online.** Alle kartdata ligger som filer i `lab/data/`
  og `lab/fliser/`, og siden bruker bare ArcGIS Maps SDK som kartmotor. Bakgrunnskartene
  kommer rett fra GeodataOnline, som før.
- **Kartet dimmes utenfor interesseområdet**: Øyeren, Svelle, Glomma og Nitelva mellom
  Lillestrøm, Sørumsand, Trøgstad og Solbergfoss, med 2 km buffer. Overgangen er myk:
  dimmingen tegnes i flere trinn med hullet bufret stadig lenger ut. Styrke og bredde
  styres med `DIM_OPACITY` og `DIM_FADE_*` øverst i `lab/index.html`.
- **Alle leder unntatt kanoleden har to haloer**: rød på vestsiden og grønn på østsiden,
  for å vise hvilken side båten skal kjøre på. Linjene er lagret fra sør mot nord, så
  vest er alltid venstre side av linjen.
- **Samferdsel er hentet ut som filer**, så kartet ikke venter på en karttjeneste for
  hver panorering. Alt tas med inntil 1 km utenfor interesseområdet. Hvert objekt har
  feltet `fade` (0–1), og lagene tones ut mot yttergrensen i stedet for å kuttes.
- **Samferdsel tynnes ut etter zoom**, målt på den lengste leden av kartbildet:
  hovedveier (europa-, riks- og fylkesveg) vises alltid, øvrige veier, traktorveier og
  anleggsveier når kartbildet dekker høyst 4 km, og parkering, buss og tog høyst 10 km.
  Grensene står øverst i `lab/index.html` (`SAMFERDSEL_VEG_KM`, `SAMFERDSEL_PUNKT_KM`).
  Fortau, gangfelt, trapper og stier er utelatt.
- **Dybdekurvene har egen fargebruk på lyse bakgrunnskart** (Gråtone og Basis terreng):
  mørkere blåtoner og mørke tall med hvit halo. På flyfoto brukes webkartets farger.
  Kurvene er delt i biter på høyst 1,5 km, som tegnes og etiketteres raskere.

### Hvor dataene kommer fra

| Fil | Innhold | Kilde |
|---|---|---|
| `data/interesseomrade.geojson` | Området som ikke dimmes | NVE Innsjødatabase og Elvenett |
| `data/dybdekurver.geojson` | Dybdekurver | NVE Innsjødatabase |
| `data/samferdsel/*.geojson` | Veier, traktorveier, parkering, buss og tog. `hovedveg` er europa-, riks- og fylkesveier, `veg` resten | GeomapSamferdsel (GeodataOnline) |
| `data/led.geojson` | Ledene | Kopi av `LedOyeren` i AGOL |
| `data/poi.geojson`, `data/poi-bilder/` | Interessepunkter med bilde | Kopi av `POI_Innsjo` i AGOL |
| `data/symbologi.json` | Symbologi og startvisning | Kopi fra webkartet i AGOL |
| `fliser/papirkart/` | Papirkartet over naturreservatet | Kopi av `Nordre_Oyeren_tif` i AGOL |

Alt er et øyeblikksbilde. Ingenting oppdateres av seg selv.

### Oppdatere dataene

Skriptet [`lab/verktoy/bygg_data.py`](lab/verktoy/bygg_data.py) henter alt på nytt.
Det krever Python med `shapely`, `pyproj` og `pillow`.

```bash
python lab/verktoy/bygg_data.py omrade dybde samferdsel   # fra NVE og GeodataOnline
python lab/verktoy/bygg_data.py agol                      # led, POI og symbologi fra AGOL
python lab/verktoy/bygg_data.py papirkart                 # papirkartflisene fra AGOL
```

Samferdsel krever innlogging i GeodataOnline. Sett et token i miljøvariabelen
`GDO_TOKEN`. Uten token brukes proxyen som webkartet i AGOL har lagret innloggingen i.
Den forsvinner hvis AGOL-kontoen legges ned.

Ledene og interessepunktene finnes foreløpig bare i AGOL. Når AGOL er borte, redigeres
`led.geojson` og `poi.geojson` direkte, for eksempel i <https://geojson.io>. Ledlinjene
(unntatt kanoleden) må gå fra sør mot nord, ellers bytter haloene side.

