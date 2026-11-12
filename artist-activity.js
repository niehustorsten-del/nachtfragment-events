/* Nachtfragment – Artist Activity display */
(() => {
  "use strict";
  const FEED_URL = "https://niehustorsten-del.github.io/nachtfragment-events/data/artist-activity.json";
  const slugMatch = window.location.pathname.match(/\\/index\\.php\\/artists\\/([a-z0-9-]+)\\/?$/i);
  if (!slugMatch) return;
  const slug = slugMatch[1].toLowerCase();
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const dateLabel = (iso) => {
    const d = new Date(iso + "T12:00:00");
    return Number.isNaN(d.getTime()) ? iso : new Intl.DateTimeFormat("de-DE", {day:"2-digit",month:"long",year:"numeric"}).format(d);
  };
  const mount = document.getElementById("nachtfragment-artist-activity") || document.createElement("div");
  mount.id = "nachtfragment-artist-activity";
  fetch(FEED_URL + "?v=" + Date.now(), {cache:"no-store"})
    .then((r) => { if (!r.ok) throw new Error("Feed nicht erreichbar"); return r.json(); })
    .then((feed) => {
      const artist = feed.artists && feed.artists[slug];
      if (!artist) return;
      const events = Array.isArray(artist.events) ? artist.events : [];
      const rows = events.map((e) => {
        const place = [e.venue, e.city].filter(Boolean).map(esc).join(" · ");
        const kind = e.category === "festival" ? "Festival" : e.category === "clubnight" ? "Clubnacht" : "Konzert";
        return '<li class="nf-activity-event"><time datetime="' + esc(e.date) + '">' + esc(dateLabel(e.date)) +
          '</time><div class="nf-activity-event-main"><a href="' + esc(e.url) +
          '" target="_blank" rel="noopener noreferrer">' + esc(e.title || artist.name) + '</a>' +
          (place ? '<span class="nf-activity-place">' + place + '</span>' : '') +
          '<span class="nf-activity-meta">' + kind + (e.source ? ' · Quelle: ' + esc(e.source) : '') +
          '</span></div></li>';
      }).join("");
      mount.innerHTML = '<section class="nf-artist-activity" aria-label="Aktuelle Künstleraktivität">' +
        '<div class="nf-activity-heading"><span class="nf-activity-kicker">NACHTFRAGMENT · ARTIST ACTIVITY</span>' +
        '<h2>Aktuelle Termine</h2></div>' +
        (rows ? '<ul class="nf-activity-list">' + rows + '</ul>' :
          '<p class="nf-activity-empty">Aktuell liegen keine bestätigten Konzerttermine vor.</p>') +
        '<p class="nf-activity-foot">Automatisch aus den veröffentlichten Nachtfragment-Konzertdaten · ' +
        '<a href="https://niehustorsten-del.github.io/nachtfragment-events/concerts.html">Zum Konzertkalender</a></p></section>';
      const heading = document.querySelector("main h1, .item-page h1, article h1, h1");
      if (heading) (heading.closest(".page-header") || heading).insertAdjacentElement("afterend", mount);
    })
    .catch((err) => console.warn("[Nachtfragment Artist Activity]", err));
})();
