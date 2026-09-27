/*
  Enkel tilgangssperre for Flyt.

  VIKTIG: Dette er en dørmatte, ikke en lås. Siden ligger på GitHub Pages, som
  bare serverer statiske filer — det finnes ingen server å gjøre sjekken på.
  Alt under kjører i nettleseren, og kildekoden ligger dessuten åpent på
  github.com/stalesteel/flyt. Sperren holder tilfeldige besøkende ute, men
  stopper ingen som kan åpne utviklerverktøy eller lese repoet.

  Passordet lagres som en saltet SHA-256-hash i stedet for klartekst, så det
  ikke står lesbart i et offentlig repo.
*/
(function (global) {
  "use strict";

  const SALT = "flyt-oyeren-2026";
  const USERNAME = "tone";
  const PASSWORD_HASH = "30d7fbeb60519bb2d5a8500f5069d04489879e3b713c9878a2dbf3625f7d8bcf";

  const STORAGE_KEY = "flyt-adgang";
  const DAYS_VALID = 90;

  function isUnlocked() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return false;
      return JSON.parse(raw).utloper > Date.now();
    } catch (err) {
      return false;
    }
  }

  function remember() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        utloper: Date.now() + DAYS_VALID * 24 * 60 * 60 * 1000
      }));
    } catch (err) {
      // Privat vindu eller blokkert lagring: brukeren må logge inn på nytt
    }
  }

  async function hash(text) {
    const bytes = new TextEncoder().encode(SALT + ":" + text);
    const digest = await crypto.subtle.digest("SHA-256", bytes);
    return Array.prototype.map
      .call(new Uint8Array(digest), function (b) { return b.toString(16).padStart(2, "0"); })
      .join("");
  }

  function buildLoginScreen(onSuccess) {
    const screen = document.createElement("div");
    screen.className = "flyt-login";
    screen.innerHTML =
      '<form class="flyt-login-card" autocomplete="on">' +
      '  <h1>Flyt</h1>' +
      '  <p>Denne siden er privat.</p>' +
      '  <label for="flyt-user">Brukernavn</label>' +
      '  <input id="flyt-user" name="username" type="text" autocapitalize="none" autocorrect="off" required>' +
      '  <label for="flyt-pass">Passord</label>' +
      '  <input id="flyt-pass" name="password" type="password" required>' +
      '  <button type="submit">Logg inn</button>' +
      '  <p class="flyt-login-error" hidden>Feil brukernavn eller passord.</p>' +
      '</form>';

    const form = screen.querySelector("form");
    const user = screen.querySelector("#flyt-user");
    const pass = screen.querySelector("#flyt-pass");
    const error = screen.querySelector(".flyt-login-error");

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      hash(pass.value).then(function (digest) {
        const ok = user.value.trim().toLowerCase() === USERNAME && digest === PASSWORD_HASH;
        if (!ok) {
          error.hidden = false;
          pass.value = "";
          pass.focus();
          return;
        }
        remember();
        screen.remove();
        document.documentElement.removeAttribute("data-locked");

        // Uten callback lastes siden på nytt. Kartet måler containeren sin ved
        // oppstart, og ville fått null størrelse mens innholdet var skjult.
        if (onSuccess) onSuccess();
        else location.reload();
      });
    });

    return screen;
  }

  // Kaller onUnlocked med en gang hvis brukeren allerede er innlogget, ellers
  // først etter at riktig brukernavn og passord er tastet inn. Uten callback
  // lastes siden på nytt etter innlogging.
  function krevAdgang(onUnlocked) {
    if (isUnlocked()) {
      if (onUnlocked) onUnlocked();
      return;
    }

    document.documentElement.setAttribute("data-locked", "true");

    function show() {
      document.body.appendChild(buildLoginScreen(onUnlocked));
      document.getElementById("flyt-user").focus();
    }

    if (document.body) show();
    else document.addEventListener("DOMContentLoaded", show);
  }

  global.FlytAuth = { krevAdgang: krevAdgang };
})(window);
