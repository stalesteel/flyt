# Flyt

Privat kart for bruk på Øyeren, med sjekklister for båten.
Ligger på **GitHub Pages** og publiseres til <https://flyt.klommestein.no> automatisk
når endringer pushes til `main`.

## Adresser

| Adresse | Hva det er |
|---|---|
| `/` | Kartet |
| `/sjekkliste` | Sjekklistene (ikke lenket fra noe sted) |
| `/sjekkliste/admin` | Redigering av sjekklistene (ikke lenket fra noe sted) |

## Tilgangssperre

Hele siden ligger bak en enkel innlogging: brukernavn **Tone**, passord **Berit**.
Store og små bokstaver spiller ingen rolle i brukernavnet; passordet må skrives nøyaktig.
Innloggingen huskes i 90 dager i nettleseren.

### Hva dette er og ikke er

Dette er en **dørmatte, ikke en lås**. GitHub Pages serverer bare statiske filer, så det
finnes ingen server å gjøre sjekken på — alt skjer i nettleseren. I tillegg er repoet
offentlig, så hvem som helst kan lese `index.html`, `sjekkliste/data.json` og bildene
direkte på GitHub uansett hva innloggingssiden sier.

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

## Sjekklister

### Innhold

Sjekklistene ligger i [`sjekkliste/data.json`](sjekkliste/data.json):

```json
{
  "lister": [
    {
      "id": "ankomst",
      "navn": "Ankomst båt – før tur",
      "punkter": [
        {
          "id": "fortoyning",
          "tittel": "Fortøyninger og fendere",
          "beskrivelse": "Sjekk at tauverk er helt og riktig festet.",
          "bilde": "bilder/fortoyning.jpg"
        }
      ]
    }
  ]
}
```

Rekkefølgen i `punkter` er rekkefølgen de vises i. Avkrysninger lagres ikke — en liste
starter alltid blank.

### Bilder

Legg bildene i [`sjekkliste/bilder/`](sjekkliste/bilder/) og vis til dem som
`bilder/filnavn.jpg` i `data.json`.

- **Format:** JPG eller WebP. WebP gir minst filer.
- **Størrelse:** stående format, rundt 900 × 1200 piksler holder godt. Maks ca. 1200 px høyde.
- **Motivet må ligge i øverste halvdel.** Bildet fyller hele skjermen og beskjæres fra
  toppen, og den nederste tredjedelen dekkes av tekstbåndet.
- Mangler bildet, vises en nøytral mørk bakgrunn i stedet for et ødelagt bilde.

`plassholder-*.svg` er midlertidige testbilder og kan slettes når du har lagt inn dine egne.

### Redigere sjekklistene

`/sjekkliste/admin` lar deg opprette og slette lister, legge til og endre punkter, og
flytte punkter opp og ned. Endringene lagres fortløpende i nettleseren din, så du ikke
mister arbeid ved en refresh.

**Endringene blir ikke publisert av seg selv.** GitHub Pages er statisk, og admin kan
ikke skrive til repoet — det ville krevd en GitHub-token i en offentlig side, altså
skriverettigheter til repoet for hvem som helst.

Slik legger du inn endringene:

1. Trykk **«Last ned data.json»** i admin.
2. Erstatt `sjekkliste/data.json` i prosjektet med filen du lastet ned.
3. Commit og push. Endringene er live etter et minutt eller to.

Bilder må legges inn på samme måte: velger du en bildefil i admin, noteres bare filnavnet.
Selve filen må du kopiere inn i `sjekkliste/bilder/` og committe.

Knappen **«Forkast endringer»** sletter utkastet i nettleseren og henter `data.json` på nytt.

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
