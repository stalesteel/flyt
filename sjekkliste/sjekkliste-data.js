/*
  Datalag for sjekklistene.

  Sjekklistene ligger i en hosted table i ArcGIS Online — samme mønster som
  interessepunktene i kartet. Det lar admin lagre rett fra mobilen, noe som
  ikke er mulig mot GitHub Pages, som bare serverer statiske filer.

  Én rad per sjekkpunkt. Listen den hører til identifiseres med ListeId, og
  navnet ligger på hver rad. Bildet lagres som attachment på raden.
*/
(function (global) {
  "use strict";

  const CONFIG = {
    url: "https://services.arcgis.com/2JyTvMWQSnM2Vi8q/arcgis/rest/services/SjekklisteFlyt/FeatureServer/0",
    felt: {
      objectId: "OBJECTID",
      listeId: "ListeId",
      listeNavn: "ListeNavn",
      tittel: "Tittel",
      beskrivelse: "Beskrivelse",
      rekkefolge: "Rekkefolge"
    }
  };

  const F = CONFIG.felt;

  function postSkjema(operasjon, felter) {
    const body = new URLSearchParams();
    body.set("f", "json");
    Object.keys(felter).forEach(function (n) { body.set(n, felter[n]); });

    return fetch(CONFIG.url + "/" + operasjon, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: body.toString()
    }).then(function (r) { return r.json(); }).then(function (json) {
      if (json.error) throw new Error(operasjon + ": " + (json.error.message || JSON.stringify(json.error)));
      return json;
    });
  }

  function sjekkResultater(json, nokkel) {
    const resultater = json[nokkel] || [];
    resultater.forEach(function (r) {
      if (!r.success) throw new Error(nokkel + " feilet: " + JSON.stringify(r));
    });
    return resultater;
  }

  // ---------------- Lesing ----------------

  // Henter alle radene og grupperer dem til lister, sortert på Rekkefolge.
  // Bilde-URL-ene hentes i samme slengen, så visningen slipper et ekstra kall.
  function hentLister() {
    const sporring = CONFIG.url + "/query?where=1%3D1&outFields=*&returnGeometry=false&f=json";

    return fetch(sporring, { cache: "no-store" })
      .then(function (r) { return r.json(); })
      .then(function (json) {
        if (json.error) throw new Error("query: " + (json.error.message || ""));
        const rader = (json.features || []).map(function (f) { return f.attributes; });
        if (!rader.length) return { lister: [] };

        return hentBilder(rader.map(function (r) { return r[F.objectId]; }))
          .then(function (bilder) { return { lister: grupper(rader, bilder) }; });
      });
  }

  function grupper(rader, bilder) {
    const etterListe = {};

    rader.forEach(function (rad) {
      const listeId = rad[F.listeId] || "uten-liste";
      if (!etterListe[listeId]) {
        etterListe[listeId] = {
          id: listeId,
          navn: rad[F.listeNavn] || "Uten navn",
          punkter: []
        };
      }
      const vedlegg = bilder[rad[F.objectId]];
      etterListe[listeId].punkter.push({
        objectId: rad[F.objectId],
        id: String(rad[F.objectId]),
        tittel: rad[F.tittel] || "",
        beskrivelse: rad[F.beskrivelse] || "",
        rekkefolge: rad[F.rekkefolge] === null || rad[F.rekkefolge] === undefined ? 0 : rad[F.rekkefolge],
        bilde: vedlegg ? vedlegg.url : null,
        attachmentId: vedlegg ? vedlegg.id : null
      });
    });

    const lister = Object.keys(etterListe).map(function (id) { return etterListe[id]; });
    lister.forEach(function (liste) {
      liste.punkter.sort(function (a, b) { return a.rekkefolge - b.rekkefolge; });
    });
    lister.sort(function (a, b) { return a.navn.localeCompare(b.navn, "nb"); });
    return lister;
  }

  function hentBilder(objectIds) {
    if (!objectIds.length) return Promise.resolve({});
    const url = CONFIG.url + "/queryAttachments?objectIds=" + objectIds.join(",") + "&f=json";

    return fetch(url, { cache: "no-store" })
      .then(function (r) { return r.json(); })
      .then(function (json) {
        const per = {};
        (json.attachmentGroups || []).forEach(function (gruppe) {
          const info = (gruppe.attachmentInfos || [])[0];
          if (!info) return;
          per[gruppe.parentObjectId] = {
            id: info.id,
            url: CONFIG.url + "/" + gruppe.parentObjectId + "/attachments/" + info.id
          };
        });
        return per;
      })
      .catch(function () { return {}; });
  }

  // ---------------- Skriving ----------------

  function nyttPunkt(punkt) {
    const attributter = {};
    attributter[F.listeId] = punkt.listeId;
    attributter[F.listeNavn] = punkt.listeNavn;
    attributter[F.tittel] = punkt.tittel || "";
    attributter[F.beskrivelse] = punkt.beskrivelse || "";
    attributter[F.rekkefolge] = punkt.rekkefolge || 0;

    return postSkjema("addFeatures", { features: JSON.stringify([{ attributes: attributter }]) })
      .then(function (json) { return sjekkResultater(json, "addResults")[0].objectId; });
  }

  function endrePunkter(endringer) {
    if (!endringer.length) return Promise.resolve();

    const features = endringer.map(function (e) {
      const attributter = {};
      attributter[F.objectId] = e.objectId;
      if ("tittel" in e) attributter[F.tittel] = e.tittel || "";
      if ("beskrivelse" in e) attributter[F.beskrivelse] = e.beskrivelse || "";
      if ("rekkefolge" in e) attributter[F.rekkefolge] = e.rekkefolge;
      if ("listeNavn" in e) attributter[F.listeNavn] = e.listeNavn;
      return { attributes: attributter };
    });

    return postSkjema("updateFeatures", { features: JSON.stringify(features) })
      .then(function (json) { sjekkResultater(json, "updateResults"); });
  }

  function slettPunkter(objectIds) {
    if (!objectIds.length) return Promise.resolve();
    return postSkjema("deleteFeatures", { objectIds: objectIds.join(",") })
      .then(function (json) { sjekkResultater(json, "deleteResults"); });
  }

  // Erstatter bildet når raden har et fra før, ellers legges det til
  function lagreBilde(objectId, blob, attachmentId) {
    const skjema = new FormData();
    skjema.set("f", "json");
    skjema.set("attachment", blob, "sjekkpunkt.jpg");

    let operasjon = "addAttachment";
    if (attachmentId) {
      skjema.set("attachmentId", attachmentId);
      operasjon = "updateAttachment";
    }

    return fetch(CONFIG.url + "/" + objectId + "/" + operasjon, { method: "POST", body: skjema })
      .then(function (r) { return r.json(); })
      .then(function (json) {
        const resultat = json.updateAttachmentResult || json.addAttachmentResult;
        if (json.error || !(resultat && resultat.success)) {
          throw new Error("Bildet ble ikke lagret: " + JSON.stringify(json));
        }
        return resultat.objectId;
      });
  }

  // Skalerer ned og komprimerer som i kartappen, så opplasting fra mobil går fort
  function komprimerBilde(fil, maksSide, kvalitet) {
    return new Promise(function (resolve, reject) {
      const bilde = new Image();
      const leser = new FileReader();

      leser.onload = function (e) {
        bilde.onload = function () {
          let b = bilde.width, h = bilde.height;
          if (b > maksSide || h > maksSide) {
            if (b > h) { h = Math.round(h * (maksSide / b)); b = maksSide; }
            else { b = Math.round(b * (maksSide / h)); h = maksSide; }
          }
          const lerret = document.createElement("canvas");
          lerret.width = b;
          lerret.height = h;
          lerret.getContext("2d").drawImage(bilde, 0, 0, b, h);
          lerret.toBlob(function (blob) {
            if (blob) resolve(blob); else reject(new Error("Klarte ikke å lese bildet"));
          }, "image/jpeg", kvalitet);
        };
        bilde.onerror = reject;
        bilde.src = e.target.result;
      };
      leser.onerror = reject;
      leser.readAsDataURL(fil);
    });
  }

  global.Sjekkliste = {
    config: CONFIG,
    hentLister: hentLister,
    nyttPunkt: nyttPunkt,
    endrePunkter: endrePunkter,
    slettPunkter: slettPunkter,
    lagreBilde: lagreBilde,
    komprimerBilde: komprimerBilde
  };
})(window);
