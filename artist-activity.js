/* Nachtfragment – Artist Activity: concerts + approved news */
(() => {
  "use strict";
  const FEED_URL="https://niehustorsten-del.github.io/nachtfragment-events/data/artist-activity.json";
  const match=window.location.pathname.match(/\/index\.php\/artists\/([a-z0-9-]+)\/?$/i);
  if(!match)return;
  const slug=match[1].toLowerCase();
  const esc=(v)=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const dateLabel=(iso)=>{
    if(!iso)return "";
    const d=new Date(iso.length===10?iso+"T12:00:00":iso);
    return Number.isNaN(d.getTime())?iso:new Intl.DateTimeFormat("de-DE",{day:"2-digit",month:"long",year:"numeric"}).format(d);
  };
  const mount=document.getElementById("nachtfragment-artist-activity")||document.createElement("div");
  mount.id="nachtfragment-artist-activity";
  if(!document.getElementById("nf-artist-activity-style")){
    const style=document.createElement("style");style.id="nf-artist-activity-style";
    style.textContent=".nf-artist-activity{margin:1.8rem 0 2.2rem;padding:1.25rem 1.4rem;background:#111116;border:1px solid #34303b;border-left:3px solid #8b6a91;color:#e8e3e9}"+
    ".nf-activity-kicker{display:block;font-size:.68rem;letter-spacing:.16em;color:#aa91b0;margin-bottom:.35rem}"+
    ".nf-activity-heading h2{margin:0 0 1rem;font-size:1.35rem;color:#f3edf4}"+
    ".nf-activity-section+.nf-activity-section{margin-top:1.5rem;padding-top:1.25rem;border-top:1px solid #38323e}"+
    ".nf-activity-section h3{margin:0 0 .7rem;color:#d8c4df;font-size:1.05rem}"+
    ".nf-activity-list{list-style:none;margin:0;padding:0}"+
    ".nf-activity-event,.nf-activity-news{display:grid;grid-template-columns:minmax(125px,165px) 1fr;gap:.8rem;padding:.8rem 0;border-top:1px solid #302c35}"+
    ".nf-activity-event time,.nf-activity-news time{font-size:.88rem;color:#c5b1cb}"+
    ".nf-activity-main{display:flex;flex-direction:column;gap:.22rem}"+
    ".nf-activity-main>a{color:#f0e8f2;text-decoration:none;font-weight:600}"+
    ".nf-activity-main>a:hover{color:#c7a5d0;text-decoration:underline}"+
    ".nf-activity-place,.nf-activity-summary{font-size:.9rem;color:#c6c0c9}"+
    ".nf-activity-meta{font-size:.76rem;color:#96909b}"+
    ".nf-activity-foot{margin:1rem 0 0;padding-top:.75rem;border-top:1px solid #302c35;font-size:.76rem;color:#96909b}"+
    ".nf-activity-foot a{color:#b89ac0}@media(max-width:600px){.nf-activity-event,.nf-activity-news{grid-template-columns:1fr;gap:.25rem}}";
    document.head.appendChild(style);
  }
  fetch(FEED_URL+"?v="+Date.now(),{cache:"no-store"})
  .then(r=>{if(!r.ok)throw new Error("Feed nicht erreichbar");return r.json();})
  .then(feed=>{
    const artist=feed.artists&&feed.artists[slug];
    if(!artist){mount.remove();return;}
    const events=Array.isArray(artist.events)?artist.events:[];
    const news=Array.isArray(artist.news)?artist.news:[];
    if(!events.length&&!news.length){mount.remove();return;}
    const eventRows=events.map(e=>{
      const place=[e.venue,e.city].filter(Boolean).map(esc).join(" · ");
      const kind=e.category==="festival"?"Festival":e.category==="clubnight"?"Clubnacht":"Konzert";
      return '<li class="nf-activity-event"><time datetime="'+esc(e.date)+'">'+esc(dateLabel(e.date))+'</time><div class="nf-activity-main"><a href="'+esc(e.url)+'" target="_blank" rel="noopener noreferrer">'+esc(e.title||artist.name)+'</a>'+(place?'<span class="nf-activity-place">'+place+'</span>':'')+'<span class="nf-activity-meta">'+kind+(e.source?' · Quelle: '+esc(e.source):'')+'</span></div></li>';
    }).join("");
    const newsRows=news.map(n=>{
      const meta=[n.category,n.publisher].filter(Boolean).map(esc).join(" · ");
      return '<li class="nf-activity-news"><time datetime="'+esc(n.date)+'">'+esc(dateLabel(n.date))+'</time><div class="nf-activity-main"><a href="'+esc(n.url)+'" target="_blank" rel="noopener noreferrer">'+esc(n.title)+'</a>'+(n.summary?'<span class="nf-activity-summary">'+esc(n.summary)+'</span>':'')+(meta?'<span class="nf-activity-meta">'+meta+'</span>':'')+'</div></li>';
    }).join("");
    mount.innerHTML='<section class="nf-artist-activity" aria-label="Aktuelle Künstleraktivität"><div class="nf-activity-heading"><span class="nf-activity-kicker">NACHTFRAGMENT · ARTIST ACTIVITY</span><h2>Aktuelles</h2></div>'+(newsRows?'<div class="nf-activity-section"><h3>News & Veröffentlichungen</h3><ul class="nf-activity-list">'+newsRows+'</ul></div>':'')+(eventRows?'<div class="nf-activity-section"><h3>Konzerte & Termine</h3><ul class="nf-activity-list">'+eventRows+'</ul></div>':'')+'<p class="nf-activity-foot">Geprüfte Künstlernews und bestätigte Konzertdaten · <a href="https://niehustorsten-del.github.io/nachtfragment-events/concerts.html">Zum Konzertkalender</a></p></section>';
    const heading=document.querySelector("main h1, .item-page h1, article h1, h1");
    if(heading)(heading.closest(".page-header")||heading).insertAdjacentElement("afterend",mount);
  }).catch(err=>console.warn("[Nachtfragment Artist Activity]",err));
})();
