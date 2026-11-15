/**
 * The director: decides when an idle film plays, and which. One shared stillness detector (no
 * scroll, pointer movement, wheel, key or touch), one film at a time, films taking turns, a
 * cooldown between them. Films register themselves; each says how long the screen must be still
 * before it may start (`idleAfter`) and whether the page currently gives it a stage (`ready`).
 *
 * Scrolling more than a little during a film aborts it; the film must then put the page back
 * exactly as it was. `?film=<name>` in the URL plays that film right away (for previews).
 */

export type FilmEntry = {
  name: string;
  /** Seconds of stillness required. */
  idleAfter: number;
  /** Films with priority are tried first (e.g. the logo film when the logo is in view). */
  priority?: number;
  ready: () => boolean;
  start: () => void;
  abort: () => void;
};

const COOLDOWN = 22;
const films = new Map<string, FilmEntry>();
let playing: string | null = null;
let playingScroll = 0;
let lastEnd = -1e9;
let lastActive = 0;
let turn = 0;
let timer = 0;
let px = 0;
let py = 0;

const now = () => performance.now() / 1000;
const forced = () =>
  typeof window === "undefined" ? null : new URLSearchParams(window.location.search).get("film");

function activity() {
  lastActive = now();
}
function onMove(e: PointerEvent) {
  if (Math.hypot(e.clientX - px, e.clientY - py) > 3) activity();
  px = e.clientX;
  py = e.clientY;
}
function onScroll() {
  activity();
  if (playing && Math.abs(window.scrollY - playingScroll) > 140) films.get(playing)?.abort();
}
function onResize() {
  if (playing) films.get(playing)?.abort();
}

function tick() {
  if (playing || document.visibilityState !== "visible") return;
  const t = now();
  const idle = t - lastActive;
  const force = forced();
  const list = [...films.values()];
  if (force) {
    const f = films.get(force);
    if (f && idle > 0.8 && t - lastEnd > 3 && f.ready()) begin(f);
    return;
  }
  // priority films first, then the others in turn
  const pri = list
    .filter((f) => (f.priority ?? 0) > 0)
    .sort((a, b) => (b.priority ?? 0) - (a.priority ?? 0));
  const rest = list.filter((f) => !(f.priority ?? 0));
  const order = [
    ...pri,
    ...rest.slice(turn % Math.max(1, rest.length)),
    ...rest.slice(0, turn % Math.max(1, rest.length)),
  ];
  for (const f of order) {
    const cool = (f.priority ?? 0) > 0 ? 4 : COOLDOWN;
    if (idle < f.idleAfter || t - lastEnd < cool) continue;
    if (!f.ready()) continue;
    if (!(f.priority ?? 0)) turn++;
    begin(f);
    return;
  }
}

function begin(f: FilmEntry) {
  playing = f.name;
  playingScroll = window.scrollY;
  window.dispatchEvent(
    new CustomEvent("relay:interlude", { detail: { active: true, film: f.name } }),
  );
  f.start();
}

/** A film calls this when it has finished (or been aborted and cleaned up). */
export function finished(name: string) {
  if (playing !== name) return;
  playing = null;
  lastEnd = now();
  lastActive = now();
  window.dispatchEvent(
    new CustomEvent("relay:interlude", { detail: { active: false, film: name } }),
  );
}

export function register(f: FilmEntry) {
  films.set(f.name, f);
  if (!timer) {
    lastActive = now();
    window.addEventListener("pointermove", onMove, { passive: true });
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("wheel", activity, { passive: true });
    window.addEventListener("keydown", activity);
    window.addEventListener("touchstart", activity, { passive: true });
    window.addEventListener("resize", onResize);
    timer = window.setInterval(tick, 400);
  }
  return () => {
    if (playing === f.name) f.abort();
    films.delete(f.name);
    if (!films.size && timer) {
      window.clearInterval(timer);
      timer = 0;
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("wheel", activity);
      window.removeEventListener("keydown", activity);
      window.removeEventListener("touchstart", activity);
      window.removeEventListener("resize", onResize);
    }
  };
}
