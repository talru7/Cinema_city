import {api, fetchJson, initializeAuth, setStatus} from './api.js';

const state = {showId: null, selected: new Map(), ticketPrice: 0};
const dateFormat = new Intl.DateTimeFormat('he-IL', {dateStyle: 'medium', timeStyle: 'short'});

document.addEventListener('DOMContentLoaded', async () => {
  try {
    await initializeAuth(document.querySelector('#auth-controls'));
    bindEvents();
    await loadShows();
  } catch (error) { setStatus(error.message, true); }
});

function bindEvents() {
  document.querySelector('#genre').addEventListener('change', loadShows);
  document.querySelector('#close-panel').addEventListener('click', () => hide('#booking-panel'));
  document.querySelector('#close-bookings').addEventListener('click', () => hide('#bookings-panel'));
  document.querySelector('#confirm-booking').addEventListener('click', confirmBooking);
  document.querySelector('#my-bookings').addEventListener('click', loadBookings);
}

async function loadShows() {
  const genre = document.querySelector('#genre').value;
  const shows = await fetchJson(`/api/shows${genre ? `?genre=${genre}` : ''}`);
  const grid = document.querySelector('#shows');
  grid.replaceChildren(...shows.map(showCard));
  setStatus(shows.length ? '' : 'לא נמצאו הקרנות בשבוע הקרוב');
}

function showCard(show) {
  const article = document.createElement('article');
  article.className = 'show-card';
  const title = document.createElement('h2'); title.textContent = show.movie_title;
  const meta = document.createElement('div'); meta.className = 'show-meta';
  meta.append(text(`אולם ${show.hall_id} · ${dateFormat.format(new Date(show.start_time))}`), text(`${show.ticket_price} ₪ לכרטיס`));
  const button = document.createElement('button'); button.className = 'button'; button.type = 'button'; button.textContent = 'בחירת מושבים';
  button.addEventListener('click', () => openSeats(show));
  article.append(title, meta, button); return article;
}

async function openSeats(screening) {
  try {
    const seats = await fetchJson(`/api/shows/${screening.show_id}/seats`);

    state.showId = screening.show_id;
    state.ticketPrice = screening.ticket_price;
    state.selected.clear();

    document.querySelector('#booking-title').textContent =
      `${screening.movie_title} - בחירת מושבים`;

    const grouped = new Map();

    seats.forEach((seat) => {
      grouped.set(
        seat.row_number,
        [...(grouped.get(seat.row_number) || []), seat]
      );
    });

    const map = document.querySelector('#seat-map');
    map.replaceChildren();

    for (const [row, rowSeats] of grouped) {
      const line = document.createElement('div');
      line.className = 'seat-row';

      const label = text(`שורה ${row}`);
      label.className = 'row-label';
      line.append(label);

      rowSeats.forEach((seat) => line.append(seatButton(seat)));
      map.append(line);
    }

    updateSummary();
    show('#booking-panel');

    document
      .querySelector('#booking-panel')
      .scrollIntoView({behavior: 'smooth'});
  } catch (error) {
    setStatus(error.message, true);
  }
}

function seatButton(seat) {
  const button = document.createElement('button'); button.type = 'button'; button.className = `seat${seat.available ? '' : ' occupied'}`;
  button.textContent = seat.seat_number; button.disabled = !seat.available;
  button.setAttribute('aria-label', `שורה ${seat.row_number}, מושב ${seat.seat_number}`);
  button.addEventListener('click', () => {
    if (state.selected.has(seat.seat_id)) state.selected.delete(seat.seat_id);
    else if (state.selected.size < 5) state.selected.set(seat.seat_id, seat);
    button.classList.toggle('selected', state.selected.has(seat.seat_id)); updateSummary();
  }); return button;
}

function updateSummary() {
  const seats = [...state.selected.values()]; const total = seats.length * state.ticketPrice;
  document.querySelector('#selection-summary').textContent = seats.length ? `${seats.length} מושבים · ${total} ₪` : 'לא נבחרו מושבים';
  document.querySelector('#confirm-booking').disabled = seats.length === 0;
}

async function confirmBooking() {
  try {
    const seats = [...state.selected.values()].map(({row_number, seat_number}) => ({row_number, seat_number}));
    const booking = await api('/api/customer/bookings', {method: 'POST', body: JSON.stringify({show_id: state.showId, seats})});
    hide('#booking-panel'); setStatus(`הזמנה מספר ${booking.booking_id} אושרה. סה"כ ${booking.total_price} ₪`); await loadShows();
  } catch (error) { setStatus(error.message, true); }
}

async function loadBookings() {
  try {
    const bookings = await api('/api/customer/bookings');
    const list = document.querySelector('#bookings-list');
    // const panel = document.querySelector('#bookings-panel');

    list.replaceChildren(...bookings.map(bookingItem));
    show('#bookings-panel');
    // panel.scrollIntoView({
      // behavior: 'smooth',
      // block: 'start',
    // });
  } catch (error) {
    setStatus(error.message, true);
  }
}

function bookingItem(booking) {
  const item = document.createElement('article'); item.className = 'booking-item';
  const details = text(`#${booking.booking_id} · ${booking.show.movie_title} · ${dateFormat.format(new Date(booking.show.start_time))} · ${booking.total_price} ₪`);
  const cancel = document.createElement('button'); cancel.className = 'button secondary'; cancel.type = 'button'; cancel.textContent = 'ביטול הזמנה';
  cancel.addEventListener('click', async () => { try { await api(`/api/customer/bookings/${booking.booking_id}`, {method: 'DELETE'}); setStatus('ההזמנה בוטלה'); await loadBookings(); } catch (error) { setStatus(error.message, true); } });
  item.append(details, cancel); return item;
}

function text(value) { const node = document.createElement('span'); node.textContent = value; return node; }
function show(selector) { document.querySelector(selector).classList.remove('hidden'); }
function hide(selector) { document.querySelector(selector).classList.add('hidden'); }
