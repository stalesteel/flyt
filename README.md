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

### Hvor innholdet ligger

Sjekklistene lagres i en **hosted table i ArcGIS Online**, ikke i repoet. Det er grunnen
til at `/sjekkliste/admin` kan lagre direkte fra mobilen — GitHub Pages er statisk og kan
ikke ta imot noe som helst.

Tjenesten: `SjekklisteFlyt/FeatureServer/0`
(URL-en står i [`sjekkliste/sjekkliste-data.js`](sjekkliste/sjekkliste-data.js).)

Én rad per sjekkpunkt, med disse feltene:

| Felt | Type | Hva det er |
|---|---|---|
| `ListeId` | String (50) | Knytter punktet til en sjekkliste |
| `ListeNavn` | String (100) | Navnet på listen, likt på alle radene i den |
| `Tittel` | String (200) | Overskriften på punktet |
| `Beskrivelse` | String (1000) | Teksten under overskriften |
| `Rekkefolge` | Integer | Rekkefølgen punktet vises i |

Bildet ligger som **attachment** på raden. Laget må ha attachments påslått, og Add,
Update og Delete tillatt under Editing.

En sjekkliste finnes bare så lenge den har minst ett punkt, siden navnet ligger på radene.
Sletter du alle punktene, forsvinner listen.

Avkrysninger lagres ikke noe sted — en liste starter alltid blank.

### Bilder

Bilder legges inn fra admin, også rett fra mobilkameraet. De skaleres ned til maks
1400 piksler og komprimeres til JPG før opplasting.

- **Motivet må ligge i øverste halvdel.** Bildet fyller hele skjermen og beskjæres fra
  toppen, og den nederste tredjedelen dekkes av tekstbåndet.
- Stående format passer best.
- Mangler bildet, vises en nøytral mørk bakgrunn i stedet for et ødelagt bilde.

### Redigere sjekklistene

`/sjekkliste/admin` lar deg opprette og slette lister, legge til og endre punkter, flytte
punkter opp og ned, og bytte bilde. **Alt lagres med én gang** og er synlig på
`/sjekkliste` umiddelbart. Tekstfelt lagres når du forlater feltet, ikke for hvert tastetrykk.

Merk at tabellen tar imot endringer fra hvem som helst som kommer gjennom innloggingen,
uten videre autentisering mot ArcGIS — samme oppsett som interessepunktene i kartet.

[`sjekkliste/data.json`](sjekkliste/data.json) er bare startinnholdet som ble lagt inn i
tabellen første gang. Filen brukes ikke av appen og kan slettes.

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
