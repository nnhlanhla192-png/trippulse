/* TripPulse shared code. Every page loads this file. */

// Change this if your API address ever changes.
const API_BASE = 'https://gzxb6hjpsf.execute-api.eu-north-1.amazonaws.com/prod';

const TRIPS_KEY = 'trippulse.trips';
const PROFILE_KEY = 'trippulse.profile';
const MAX_TRIPS = 20;

const STATUS = {
  in_progress: { label: 'On the way',     cls: 'amber' },
  arrived:     { label: 'Arrived safely', cls: 'green' },
  alert_sent:  { label: 'Alert sent',     cls: 'red'   },
  missing:     { label: 'Not found',      cls: 'grey'  },
};

const $ = (id) => document.getElementById(id);

// Build elements with text only, so nothing typed by a user is ever run as HTML.
function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === 'class') node.className = v;
    else if (k.startsWith('on')) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v);
  }
  for (const c of children) node.append(c);
  return node;
}

/* ---------- saved data (stays in this browser) ---------- */

function read(key, fallback) {
  try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; }
}
function write(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* storage may be blocked */ }
}

let trips = read(TRIPS_KEY, []);

/* ---------- time helpers ---------- */

// The server stores times in UTC without a "Z". Turn them back into a real Date.
function parseUtc(str) {
  const trimmed = String(str).replace(/(\.\d{3})\d+/, '$1');
  const hasZone = /Z$|[+-]\d\d:\d\d$/.test(trimmed);
  return new Date(hasZone ? trimmed : trimmed + 'Z');
}
function fmt(str) {
  const d = parseUtc(str);
  return isNaN(d) ? String(str) : d.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' });
}
// <input type="datetime-local"> wants "YYYY-MM-DDTHH:MM" in local time.
function toLocalInput(d) {
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
}
// The alert checker works in UTC, so send the arrival time as UTC.
function toUtcString(localValue) {
  return new Date(localValue).toISOString().slice(0, 19);
}

/* ---------- talking to the API ---------- */

async function api(path, options) {
  let res;
  try {
    res = await fetch(API_BASE + path, options);
  } catch {
    throw new Error('Could not reach TripPulse. Check your internet connection. If it keeps happening, CORS may not be switched on in API Gateway yet.');
  }
  let data = null;
  try { data = await res.json(); } catch { /* no body */ }
  if (!res.ok) throw new Error((data && data.message) || `Something went wrong (error ${res.status}).`);
  return data;
}

// Show a message in a box. "link" is optional: { href, label }.
function say(target, text, kind, link) {
  if (!text) { target.replaceChildren(); return; }
  const box = el('div', { class: 'msg ' + kind }, text);
  if (link) box.append(' ', el('a', { href: link.href }, link.label));
  target.replaceChildren(box);
}

/* ---------- page: Start a trip (index.html) ---------- */

function initStartPage() {
  function setArrival(minutesFromNow) {
    $('arrival').value = toLocalInput(new Date(Date.now() + minutesFromNow * 60000));
    updateHint();
  }

  function updateHint() {
    const v = $('arrival').value;
    $('arrival-hint').textContent = v && new Date(v) <= new Date()
      ? 'That time has already passed, so an alert goes out at the next check (within about 5 minutes).'
      : '';
  }

  [['1 min (demo)', 1], ['30 min', 30], ['1 hour', 60], ['2 hours', 120]].forEach(([label, mins]) => {
    $('chips').append(el('button', { class: 'chip', type: 'button', onclick: () => setArrival(mins) }, label));
  });
  $('arrival').addEventListener('input', updateHint);

  const profile = read(PROFILE_KEY, {});
  $('userName').value = profile.userName || '';
  $('contactName').value = profile.contactName || '';
  $('contactInfo').value = profile.contactInfo || '';
  setArrival(60);

  $('trip-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = $('start-btn');
    const msg = $('start-msg');
    btn.disabled = true;
    btn.textContent = 'Starting...';
    say(msg, '');

    const payload = {
      userName: $('userName').value.trim(),
      contactName: $('contactName').value.trim(),
      contactPhoneOrEmail: $('contactInfo').value.trim(),
      expectedArrivalTime: toUtcString($('arrival').value),
    };

    try {
      const data = await api('/trips', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      write(PROFILE_KEY, {
        userName: payload.userName,
        contactName: payload.contactName,
        contactInfo: payload.contactPhoneOrEmail,
      });
      trips.unshift({
        tripId: data.tripId,
        userName: payload.userName,
        contactName: payload.contactName,
        expectedArrivalTime: payload.expectedArrivalTime,
        status: 'in_progress',
      });
      trips = trips.slice(0, MAX_TRIPS);
      write(TRIPS_KEY, trips);
      say(msg,
        `Trip started. If you haven't checked in by ${fmt(payload.expectedArrivalTime)}, ${payload.contactName} will be alerted.`,
        'ok', { href: 'trips.html', label: 'View my trips' });
      setArrival(60);
    } catch (err) {
      say(msg, err.message, 'error');
    } finally {
      btn.disabled = false;
      btn.textContent = 'Start trip';
    }
  });
}

/* ---------- page: My trips (trips.html) ---------- */

function initTripsPage() {
  function tripCard(t) {
    const s = STATUS[t.status] || { label: 'Unknown', cls: 'grey' };
    const actions = el('div', { class: 'row' });
    if (t.status === 'in_progress' || t.status === 'alert_sent') {
      actions.append(el('button', { class: 'btn primary', type: 'button', onclick: (e) => checkIn(t.tripId, e.currentTarget) }, "I've arrived safely"));
    }
    actions.append(el('button', { class: 'btn', type: 'button', onclick: (e) => copyId(t.tripId, e.currentTarget) }, 'Copy ID'));
    actions.append(el('button', { class: 'btn ghost', type: 'button', onclick: () => removeTrip(t.tripId) }, 'Remove'));

    return el('article', { class: 'trip' },
      el('div', { class: 'trip-head' },
        el('strong', {}, t.userName),
        el('span', { class: 'badge ' + s.cls }, s.label)),
      el('p', { class: 'muted' }, `Alerts ${t.contactName} if you haven't checked in by ${fmt(t.expectedArrivalTime)}.`),
      el('code', { class: 'id' }, t.tripId),
      actions);
  }

  function render() {
    const list = $('trip-list');
    list.replaceChildren();
    if (!trips.length) {
      list.append(el('p', { class: 'muted' }, 'No trips yet. Start one on the ',
        el('a', { href: 'index.html' }, 'Start a trip'), ' page and it will show up here.'));
      return;
    }
    trips.forEach((t) => list.append(tripCard(t)));
  }

  async function refreshAll() {
    if (!trips.length) return;
    const btn = $('refresh-btn');
    btn.disabled = true;
    await Promise.all(trips.map(async (t) => {
      try {
        const fresh = await api('/trips/' + encodeURIComponent(t.tripId));
        t.status = fresh.status;
      } catch (err) {
        if (/not found/i.test(err.message)) t.status = 'missing';
        // any other error (like being offline): keep the last known status
      }
    }));
    write(TRIPS_KEY, trips);
    render();
    btn.disabled = false;
  }

  async function checkIn(tripId, button) {
    button.disabled = true;
    button.textContent = 'Checking in...';
    try {
      await api('/trips/' + encodeURIComponent(tripId), { method: 'PATCH' });
      const t = trips.find((x) => x.tripId === tripId);
      if (t) t.status = 'arrived';
      write(TRIPS_KEY, trips);
      render();
      say($('list-msg'), 'Checked in. No alert will be sent for that trip.', 'ok');
    } catch (err) {
      button.disabled = false;
      button.textContent = "I've arrived safely";
      say($('list-msg'), err.message, 'error');
    }
  }

  async function copyId(tripId, button) {
    try {
      await navigator.clipboard.writeText(tripId);
      button.textContent = 'Copied';
      setTimeout(() => { button.textContent = 'Copy ID'; }, 1500);
    } catch {
      say($('list-msg'), 'Could not copy automatically. Select the ID and copy it by hand.', 'error');
    }
  }

  function removeTrip(tripId) {
    trips = trips.filter((t) => t.tripId !== tripId);
    write(TRIPS_KEY, trips);
    render();
  }

  $('refresh-btn').addEventListener('click', () => { say($('list-msg'), ''); refreshAll(); });
  setInterval(refreshAll, 30000);
  render();
  refreshAll();
}

/* ---------- page: Look up a trip (lookup.html) ---------- */

function initLookupPage() {
  $('lookup-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const out = $('lookup-result');
    const id = $('lookup-id').value.trim();
    out.replaceChildren();
    if (!id) return;
    try {
      const t = await api('/trips/' + encodeURIComponent(id));
      const s = STATUS[t.status] || { label: t.status, cls: 'grey' };
      out.append(el('dl', {},
        el('dt', {}, 'Traveler'),     el('dd', {}, t.userName),
        el('dt', {}, 'Alerts'),       el('dd', {}, t.contactName),
        el('dt', {}, 'Started'),      el('dd', {}, fmt(t.startTime)),
        el('dt', {}, 'Expected by'),  el('dd', {}, fmt(t.expectedArrivalTime)),
        el('dt', {}, 'Status'),       el('dd', {}, el('span', { class: 'badge ' + s.cls }, s.label))));
    } catch (err) {
      say(out, err.message, 'error');
    }
  });
}

/* ---------- footer (same on every page) ---------- */

const apiLabel = $('api-label');
if (apiLabel) apiLabel.textContent = new URL(API_BASE).host;