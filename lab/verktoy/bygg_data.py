"""Henter og bygger alle dataene som /lab bruker, slik at siden kan kjøre uten
ArcGIS Online.

Kjøres fra repoets rot:

    python lab/verktoy/bygg_data.py omrade dybde samferdsel
    python lab/verktoy/bygg_data.py agol          # engangsuttrekk fra AGOL
    python lab/verktoy/bygg_data.py papirkart     # engangsuttrekk fra AGOL

Trinnene:

  omrade      Interesseområdet: Øyeren, Svelle, Glomma og Nitelva mellom
              Lillestrøm, Sørumsand, Trøgstad og Solbergfoss, med 2 km buffer.
              Kilde: NVE (åpne tjenester).
  dybde       Dybdekurvene innenfor interesseområdet. Kilde: NVE.
  samferdsel  Veier, parkering, holdeplasser og traktorveier inntil 1 km utenfor
              interesseområdet, og store veier inntil 20 km utenfor. Hvert
              objekt får et felt "fade" (0–1) som tones ut mot yttergrensen.
              Kilde: GeomapSamferdsel i GeodataOnline.
              Krever token i miljøvariabelen GDO_TOKEN. Uten token brukes
              proxyen som webkartet i AGOL har lagret innloggingen i.
  agol        Led, interessepunkter med bilder og symbologien fra webkartet.
              Dette er data som bare finnes i AGOL, så trinnet trengs bare
              så lenge AGOL-kopien er den som oppdateres.
  papirkart   Flisene til papirkartet over Nordre Øyeren naturreservat.

Krever: pip install shapely pyproj pillow
"""

import concurrent.futures as cf
import io
import json
import math
import os
import sys
import urllib.parse
import urllib.request

from pyproj import Transformer
from shapely.geometry import LineString, MultiLineString, Point, Polygon, mapping, shape
from shapely.ops import linemerge, transform, unary_union

ROT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DATA = os.path.join(ROT, "data")

NVE = "https://kart.nve.no/enterprise/rest/services"
AGOL = "https://services.arcgis.com/2JyTvMWQSnM2Vi8q/arcgis/rest/services"
WEBMAP_ID = "d275f3cbd6be4f6f9a3196e1ecd3d202"
PAPIRKART = "https://tiles.arcgis.com/tiles/2JyTvMWQSnM2Vi8q/arcgis/rest/services/Nordre_Oyeren_tif/MapServer"
GDO_SAMFERDSEL = "https://services.geodataonline.no/arcgis/rest/services/Geomap_UTM33_EUREF89/GeomapSamferdsel/MapServer"
AGOL_PROXY_SAMFERDSEL = ("https://utility.arcgis.com/usrsvcs/servers/fad9153bb5e04880a60b5b46d3d734e7"
                         "/rest/services/Geomap_UTM33_EUREF89/GeomapSamferdsel/MapServer")

til_utm = Transformer.from_crs(4326, 25833, always_xy=True).transform
til_wgs = Transformer.from_crs(25833, 4326, always_xy=True).transform

# Avstand fra vannet til kanten av interesseområdet
OMRADE_BUFFER_M = 2000

# Samferdsel tas med et stykke utenfor interesseområdet og fades ut mot
# kanten, så det ikke blir en hard grense. Avstandene er fra interesseområdet.
SAMFERDSEL_FADE_M = (0, 1000)          # full styrke ved kanten, borte etter 1 km
STOR_VEG_FADE_M = (10000, 20000)       # store veier: full til 10 km, borte etter 20 km
STOR_VEG_KATEGORI = ("E", "R", "F")    # Europa-, riks- og fylkesveg
STOR_VEG_TYPE = ("Enkel bilveg", "Kanalisert veg", "Rampe", "Rundkjøring")

# Stedene som avgrenser vassdraget. Hjørnene i et firkantpolygon, i rekkefølge.
AVGRENSNING = [
    ("Lillestrøm", 11.050, 59.956),
    ("Sørumsand", 11.2415, 59.9862),
    ("Trøgstad", 11.315, 59.640),
    ("Solbergfoss", 11.150, 59.636),
]


# ---------------------------------------------------------------------------
# Hjelpere
# ---------------------------------------------------------------------------
def hent_json(url, params=None, post=False):
    data = None
    if params:
        kodet = urllib.parse.urlencode(params)
        if post:
            data = kodet.encode()
        else:
            url += ("&" if "?" in url else "?") + kodet
    with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=120) as svar:
        resultat = json.load(svar)
    if isinstance(resultat, dict) and "error" in resultat:
        raise RuntimeError(f"{url}: {resultat['error']}")
    return resultat


def spor_alle(lag_url, params, token=None):
    """Kjører query med paging til alt er hentet. Returnerer Esri JSON-features."""
    # Uten fast sortering kan sidene overlappe, så de sorteres på objectid og
    # dubletter fjernes for sikkerhets skyld
    oid = params.pop("oidFelt", "objectid")
    felt = params.get("outFields", "")
    if oid.lower() not in felt.lower().split(","):
        params["outFields"] = (felt + "," + oid).strip(",")
    features = {}
    offset = 0
    while True:
        p = dict(f="json", where="1=1", outSR=25833, resultOffset=offset, resultRecordCount=1000,
                 orderByFields=oid)
        p.update(params)
        if token:
            p["token"] = token
        svar = hent_json(lag_url + "/query", p, post=True)
        side = svar.get("features", [])
        for f in side:
            features[f["attributes"][oid]] = f
        if not side or not svar.get("exceededTransferLimit"):
            return list(features.values())
        offset += len(side)


def esri_til_shapely(geom):
    if geom is None:
        return None
    if "x" in geom:
        return Point(geom["x"], geom["y"])
    if "paths" in geom:
        linjer = [LineString(p) for p in geom["paths"] if len(p) > 1]
        return linjer[0] if len(linjer) == 1 else MultiLineString(linjer)
    if "rings" in geom:
        # Hull (øyer) fylles bevisst igjen: her trengs bare ytterkanten av vannet
        return unary_union([Polygon(r) for r in geom["rings"]]).buffer(0)
    raise ValueError(geom)


def avrund(koordinater, desimaler):
    if isinstance(koordinater[0], (int, float)):
        return [round(koordinater[0], desimaler), round(koordinater[1], desimaler)]
    return [avrund(k, desimaler) for k in koordinater]


def som_feature(geom_utm, egenskaper, desimaler=6):
    g = mapping(transform(til_wgs, geom_utm))
    return {"type": "Feature", "properties": egenskaper,
            "geometry": {"type": g["type"], "coordinates": avrund(g["coordinates"], desimaler)}}


def skriv_geojson(sti, features):
    os.makedirs(os.path.dirname(sti), exist_ok=True)
    with open(sti, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"type": "FeatureCollection", "features": features}, f,
                  ensure_ascii=False, separators=(",", ":"))
    print(f"  {os.path.relpath(sti, ROT)}: {len(features)} objekter, {os.path.getsize(sti) / 1e3:.0f} kB")


def les_omrade():
    sti = os.path.join(DATA, "interesseomrade.geojson")
    with open(sti, encoding="utf-8") as f:
        return transform(til_utm, shape(json.load(f)["features"][0]["geometry"]))


def omrade_som_esri(omrade):
    return json.dumps({"rings": [list(omrade.exterior.coords)], "spatialReference": {"wkid": 25833}})


# ---------------------------------------------------------------------------
# Trinn
# ---------------------------------------------------------------------------
def bygg_omrade():
    print("Interesseområde")
    avgrensning = Polygon([til_utm(lon, lat) for _, lon, lat in AVGRENSNING]).buffer(1500)
    boks = ",".join(str(v) for v in avgrensning.bounds)
    felles = dict(geometry=boks, geometryType="esriGeometryEnvelope", inSR=25833,
                  spatialRel="esriSpatialRelIntersects", outSR=25833, f="json")

    # Elvenettet har Glomma under navnet "Glommavassdraget"
    elver = hent_json(NVE + "/Elvenett1/MapServer/2/query",
                      dict(felles, where="elvenavn in ('Glommavassdraget','Nitelva')", outFields="elvenavn"))
    elvelinjer = unary_union([esri_til_shapely(f["geometry"]) for f in elver["features"]]).intersection(avgrensning)

    sjoer = hent_json(NVE + "/Innsjodatabase2/MapServer/5/query",
                      dict(felles, where="elvenavnhierarki in ('Glommavassdraget','Nitelva/Glommavassdraget')",
                           outFields="navn"))
    vannflater = []
    for f in sjoer["features"]:
        flate = esri_til_shapely(f["geometry"])
        # Innsjøene elvelinjen går gjennom er deler av selve elveløpet
        if f["attributes"].get("navn") in ("Øyeren", "Svelle") or flate.intersects(elvelinjer):
            vannflater.append(flate.intersection(avgrensning))

    vann = unary_union(vannflater + [elvelinjer.buffer(80)])
    omrade = vann.buffer(OMRADE_BUFFER_M, resolution=8).simplify(25)
    # Øyer og holmer inne i området skal heller ikke dimmes
    deler = [omrade] if omrade.geom_type == "Polygon" else list(omrade.geoms)
    omrade = unary_union([Polygon(p.exterior) for p in deler])
    print(f"  {omrade.area / 1e6:.0f} km², {omrade.geom_type}")
    skriv_geojson(os.path.join(DATA, "interesseomrade.geojson"),
                  [som_feature(omrade, {"navn": "Interesseområde"})])


def bygg_dybde():
    print("Dybdekurver")
    omrade = les_omrade()
    features = spor_alle(NVE + "/Innsjodatabase2/MapServer/2", dict(
        geometry=omrade_som_esri(omrade), geometryType="esriGeometryPolygon", inSR=25833,
        spatialRel="esriSpatialRelIntersects", outFields="innsjonavn,dybde_m"))
    ut = []
    for f in features:
        geom = esri_til_shapely(f["geometry"]).simplify(1)
        a = f["attributes"]
        ut.append(som_feature(geom, {"dybde_m": a["dybde_m"], "innsjonavn": a["innsjonavn"]}, 6))
    skriv_geojson(os.path.join(DATA, "dybdekurver.geojson"), ut)


# Sublagene fra GeomapSamferdsel som tas med, og feltene som beholdes
SAMFERDSEL = {
    "veg": (21, ["vegkategori"]),
    "anleggsveg": (22, []),
    "traktorveg": (25, []),
    "traktorvegsperring": (24, []),
    "parkering": (14, ["navn", "referanse", "type", "bruksområde", "innfartsparkering",
                       "antall_parkeringsplasser_små_k", "antall_parkeringsplasser_store_",
                       "antall_avgiftsfrie_plasser", "antall_avgiftsbelagte_plasser",
                       "plasser_reservert_handikappede", "antall_ladeplasser", "avgift",
                       "avgifts__restriksjonsinfo", "adresse", "eier", "parkeringstilbyder_navn"]),
    "buss": (1, ["name", "stoptypename", "shortname", "zone_name", "description"]),
    "tog": (5, ["name", "stoptypename", "shortname", "zone_name", "description"]),
}


class Fade:
    """Deler objekter i biter etter avstand fra interesseområdet og gir hver bit
    en styrke fra 1 (innenfor start) til 0 (ved slutt)."""

    def __init__(self, omrade, start, slutt, steg):
        self.start, self.slutt = start, slutt
        self.full = omrade.buffer(start).simplify(10) if start else omrade
        self.ytre = omrade.buffer(slutt).simplify(20)
        grenser = [start + (slutt - start) * i / steg for i in range(steg + 1)]
        self.baand = []
        indre = self.full
        for d0, d1 in zip(grenser, grenser[1:]):
            ytre = omrade.buffer(d1).simplify(15)
            # Styrken midt i båndet
            self.baand.append((ytre.difference(indre), 1 - ((d0 + d1) / 2 - start) / (slutt - start)))
            indre = ytre

    def del_opp(self, geom):
        """Gir [(geometri, styrke)]."""
        if self.full.contains(geom):
            return [(geom, 1.0)]
        if geom.geom_type == "Point":
            if self.full.contains(geom):
                return [(geom, 1.0)]
            for baand, styrke in self.baand:
                if baand.contains(geom):
                    return [(geom, styrke)]
            return []
        biter = []
        inne = geom.intersection(self.full)
        if not inne.is_empty:
            biter.append((inne, 1.0))
        for baand, styrke in self.baand:
            if not baand.intersects(geom):
                continue
            bit = geom.intersection(baand)
            # Bare linjebiter; punkter der linjen bare berører et bånd hoppes over
            if bit.geom_type == "GeometryCollection":
                bit = unary_union([g for g in bit.geoms if g.geom_type in ("LineString", "MultiLineString")])
            if not bit.is_empty and bit.length > 0.5:
                biter.append((bit, styrke))
        return biter


def hent_samferdsel(base, token, lag_id, felt, flate, where="1=1"):
    return spor_alle(f"{base}/{lag_id}", dict(
        geometry=omrade_som_esri(flate), geometryType="esriGeometryPolygon", inSR=25833,
        spatialRel="esriSpatialRelIntersects", outFields=",".join(felt), where=where,
        maxAllowableOffset=0.5), token)


def fadede_features(features, felt, fade, filter=None, slaa_sammen=False, forenkle=0):
    """GeoJSON-features med feltet fade. slaa_sammen kobler linjebiter med like
    egenskaper til lengre linjer, som gir langt færre objekter og mindre filer."""
    grupper = {}
    ut = []
    for f in features:
        geom = esri_til_shapely(f["geometry"])
        if geom is None or geom.is_empty:
            continue
        a = f["attributes"]
        if filter and not filter(a):
            continue
        egenskaper = {k: v for k, v in a.items() if k in felt and v not in (None, "")}
        for bit, styrke in fade.del_opp(geom):
            if styrke < 0.03:
                continue
            e = dict(egenskaper, fade=round(styrke, 2))
            if slaa_sammen:
                grupper.setdefault(json.dumps(e, sort_keys=True, ensure_ascii=False), []).append(bit)
            else:
                # 5 desimaler er rundt en meter, godt nok for veier og punkter
                ut.append(som_feature(bit, e, 5))

    for nokkel, biter in grupper.items():
        e = json.loads(nokkel)
        linjer = linemerge(unary_union(biter))
        if forenkle:
            linjer = linjer.simplify(forenkle)
        for linje in (linjer.geoms if hasattr(linjer, "geoms") else [linjer]):
            if linje.length > 0.5:
                ut.append(som_feature(linje, e, 5))
    return ut


def bygg_samferdsel():
    print("Samferdsel")
    token = os.environ.get("GDO_TOKEN")
    base = GDO_SAMFERDSEL if token else AGOL_PROXY_SAMFERDSEL
    print("  kilde:", "GeodataOnline med token" if token else "AGOL-proxyen (sett GDO_TOKEN for å gå direkte)")
    omrade = les_omrade()

    naer = Fade(omrade, *SAMFERDSEL_FADE_M, steg=10)
    for navn, (lag_id, felt) in SAMFERDSEL.items():
        features = hent_samferdsel(base, token, lag_id, felt, naer.ytre)
        # De store veiene ligger i et eget lag som når mye lenger ut
        filter = (lambda a: a.get("vegkategori") not in STOR_VEG_KATEGORI) if navn == "veg" else None
        linjelag = navn in ("veg", "traktorveg", "anleggsveg")
        skriv_geojson(os.path.join(DATA, "samferdsel", navn + ".geojson"),
                      fadede_features(features, felt, naer, filter, slaa_sammen=linjelag, forenkle=1.5))

    fjern = Fade(omrade, *STOR_VEG_FADE_M, steg=20)
    where = "vegkategori in ({}) and typeveg in ({})".format(
        ",".join(f"'{k}'" for k in STOR_VEG_KATEGORI), ",".join(f"'{t}'" for t in STOR_VEG_TYPE))
    features = hent_samferdsel(base, token, 21, ["vegkategori"], fjern.ytre.simplify(200), where)
    skriv_geojson(os.path.join(DATA, "samferdsel", "stor_veg.geojson"),
                  fadede_features(features, ["vegkategori"], fjern, slaa_sammen=True, forenkle=3))


def bygg_agol():
    print("Led, interessepunkter og symbologi fra AGOL")
    from PIL import Image, ImageOps

    # Led: alle linjer unntatt kanoleden snus så de går fra sør mot nord. Da
    # ligger vest alltid til venstre og øst til høyre, og haloene (rød mot vest,
    # grønn mot øst) kan forskyves med en vanlig venstre/høyre-forskyvning.
    led = spor_alle(AGOL + "/LedOyeren/FeatureServer/1", dict(outFields="Led,Hastighet,Info", oidFelt="OBJECTID"))
    ut = []
    for f in led:
        geom = esri_til_shapely(f["geometry"])
        a = f["attributes"]
        if a["Led"] != 4 and geom.geom_type == "LineString" and geom.coords[0][1] > geom.coords[-1][1]:
            geom = LineString(list(geom.coords)[::-1])
        ut.append(som_feature(geom, {k: a[k] for k in ("Led", "Hastighet", "Info") if a.get(k) is not None}))
    skriv_geojson(os.path.join(DATA, "led.geojson"), ut)

    # Interessepunkter, med første vedlegg lagret som et nedskalert bilde
    poi_url = AGOL + "/POI_Innsjo/FeatureServer/0"
    poi = spor_alle(poi_url, dict(outFields="OBJECTID,Title,Description", oidFelt="OBJECTID"))
    oids = [str(f["attributes"]["OBJECTID"]) for f in poi]
    vedlegg = hent_json(poi_url + "/queryAttachments", dict(objectIds=",".join(oids), f="json"))
    bilde_for = {g["parentObjectId"]: g["attachmentInfos"][0] for g in vedlegg.get("attachmentGroups", [])
                 if g.get("attachmentInfos")}
    bildemappe = os.path.join(DATA, "poi-bilder")
    os.makedirs(bildemappe, exist_ok=True)
    ut = []
    for nr, f in enumerate(sorted(poi, key=lambda f: f["attributes"]["OBJECTID"]), start=1):
        if not f.get("geometry"):
            continue
        a = f["attributes"]
        egenskaper = {"id": nr, "tittel": a.get("Title") or "", "beskrivelse": a.get("Description") or ""}
        info = bilde_for.get(a["OBJECTID"])
        if info:
            with urllib.request.urlopen(f"{poi_url}/{a['OBJECTID']}/attachments/{info['id']}", timeout=120) as svar:
                bilde = Image.open(io.BytesIO(svar.read()))
            bilde = ImageOps.exif_transpose(bilde).convert("RGB")
            bilde.thumbnail((1600, 1600))
            filnavn = f"{nr}.jpg"
            bilde.save(os.path.join(bildemappe, filnavn), "JPEG", quality=78, optimize=True)
            egenskaper["bilde"] = "data/poi-bilder/" + filnavn
        ut.append(som_feature(esri_til_shapely(f["geometry"]), egenskaper))
    skriv_geojson(os.path.join(DATA, "poi.geojson"), ut)

    # Symbologien hentes rett fra webkartet, så lab-versjonen ser lik ut
    webkart = hent_json(f"https://www.arcgis.com/sharing/rest/content/items/{WEBMAP_ID}/data", dict(f="json"))
    lag = {l["title"]: l for l in webkart["operationalLayers"]}
    nve = next(s for s in lag["Innsjodatabase2"]["layers"] if s["id"] == 2)["layerDefinition"]["drawingInfo"]
    symbologi = {
        "led": lag["LedOyeren"]["layerDefinition"]["drawingInfo"]["renderer"],
        "poi": lag["POI_Innsjo"]["layerDefinition"]["drawingInfo"]["renderer"],
        "poiEffekt": lag["POI_Innsjo"].get("effect"),
        "dybde": nve["renderer"],
        "dybdeEtiketter": nve.get("labelingInfo"),
        "startvisning": webkart["initialState"]["viewpoint"],
    }
    with open(os.path.join(DATA, "symbologi.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(symbologi, f, ensure_ascii=False, indent=1)
    print("  data/symbologi.json")


def bygg_papirkart():
    print("Papirkart")
    info = hent_json(PAPIRKART, dict(f="json"))
    ti, ext = info["tileInfo"], info["fullExtent"]
    ox, oy = ti["origin"]["x"], ti["origin"]["y"]
    jobber = []
    for lod in ti["lods"]:
        if not info["minLOD"] <= lod["level"] <= info["maxLOD"]:
            continue
        spenn = ti["rows"] * lod["resolution"]
        for rad in range(math.floor((oy - ext["ymax"]) / spenn), math.floor((oy - ext["ymin"]) / spenn) + 1):
            for kol in range(math.floor((ext["xmin"] - ox) / spenn), math.floor((ext["xmax"] - ox) / spenn) + 1):
                jobber.append((lod["level"], rad, kol))

    mappe = os.path.join(ROT, "fliser", "papirkart")

    def hent(jobb):
        z, rad, kol = jobb
        # Tjenesten blander JPEG og PNG. Alt lagres som .png; nettleseren leser
        # bildeformatet fra innholdet, ikke filnavnet.
        sti = os.path.join(mappe, str(z), str(rad), f"{kol}.png")
        if os.path.exists(sti):
            return 0
        with urllib.request.urlopen(f"{PAPIRKART}/tile/{z}/{rad}/{kol}", timeout=60) as svar:
            data = svar.read()
        os.makedirs(os.path.dirname(sti), exist_ok=True)
        with open(sti, "wb") as f:
            f.write(data)
        return len(data)

    with cf.ThreadPoolExecutor(16) as ex:
        totalt = sum(ex.map(hent, jobber))
    print(f"  {len(jobber)} fliser, {totalt / 1e6:.1f} MB nye")


TRINN = {"omrade": bygg_omrade, "dybde": bygg_dybde, "samferdsel": bygg_samferdsel,
         "agol": bygg_agol, "papirkart": bygg_papirkart}

if __name__ == "__main__":
    valgt = sys.argv[1:] or ["omrade", "dybde", "samferdsel"]
    for navn in valgt:
        if navn not in TRINN:
            sys.exit(f"Ukjent trinn: {navn}. Velg blant {', '.join(TRINN)}")
        TRINN[navn]()
