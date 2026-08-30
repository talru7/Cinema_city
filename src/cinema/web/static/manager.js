import {api, fetchJson, initializeAuth, setStatus} from './api.js';

document.addEventListener('DOMContentLoaded', async () => {
  try {
    await initializeAuth(document.querySelector('#auth-controls'));
    bindForms(); await refreshMovies(); await refreshReport();
  } catch (error) { setStatus(error.message, true); }
});

function bindForms() {
  document.querySelector('#movie-form').addEventListener('submit', submitMovie);
  document.querySelector('#schedule-form').addEventListener('submit', submitSchedule);
  document.querySelector('#refresh-report').addEventListener('click', refreshReport);
  document.querySelector('[name="screening_date"]').valueAsDate = new Date();
  document.querySelector('#load-schedule').addEventListener('click', loadSchedule);
  document.querySelector('#schedule-hall-filter').addEventListener('change', loadSchedule);
}

async function submitMovie(event) {
  event.preventDefault();
  const form = event.currentTarget;

  try {
    // const data = Object.fromEntries(new FormData(event.currentTarget));
    const data = Object.fromEntries(new FormData(form));
    data.duration_minutes = Number(data.duration_minutes);
    data.ticket_price = Number(data.ticket_price);

    const movie = await api('/api/manager/movies', {
      method: 'POST',
      body: JSON.stringify(data),
    });

    setStatus(`הסרט ${movie.title} נוסף בהצלחה. כדי שיופיע ללקוחות, יש לתזמן עבורו הקרנה`);
    form.reset();
    await refreshMovies();
    await refreshReport();
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function submitSchedule(event) {
  event.preventDefault();
  try {
    const data = Object.fromEntries(new FormData(event.currentTarget));
    data.movie_id = Number(data.movie_id);
    data.shows_count = Number(data.shows_count);
    data.hall_id = data.hall_id ? Number(data.hall_id) : null;
    
    const shows = await api('/api/manager/shows', {method: 'POST', body: JSON.stringify(data)});
    setStatus(`${shows.length} הקרנות נוספו ללוח`);
    await refreshReport();
    await loadSchedule();
  } catch (error) { setStatus(error.message, true); }
}

async function refreshMovies() {
  const movies = await fetchJson('/api/movies'); const select = document.querySelector('#movie-select');
  select.replaceChildren(...movies.map(movie => { const option = document.createElement('option'); option.value = movie.movie_id; option.textContent = movie.title; return option; }));
}

async function refreshReport() {
  try {
    const report = await api('/api/manager/report');
    const metrics = [['סרטים', report.movies], ['הקרנות', report.shows], ['הזמנות', report.bookings], ['מושבים מוזמנים', report.booked_seats], ['הכנסות', `${report.revenue_nis} ₪`]];
    document.querySelector('#report').replaceChildren(...metrics.map(([label, value]) => { const item = document.createElement('div'); item.className = 'metric'; const name = document.createElement('span'); name.textContent = label; const number = document.createElement('strong'); number.textContent = value; item.append(name, number); return item; }));
  } catch (error) { setStatus(error.message, true); }
}

const scheduleDateFormat = new Intl.DateTimeFormat('he-IL', {
  weekday: 'short',
  day: 'numeric',
  month: 'short',
  hour: '2-digit',
  minute: '2-digit',
});

async function loadSchedule() {
  try {
    const selectedHall =
      document.querySelector('#schedule-hall-filter').value;

    const screenings = await fetchJson('/api/shows');

    const visibleScreenings = selectedHall
      ? screenings.filter(
          (screening) => screening.hall_id === Number(selectedHall)
        )
      : screenings;

    const results = document.querySelector('#schedule-results');

    if (!visibleScreenings.length) {
      const message = document.createElement('p');
      message.className = 'schedule-empty';
      message.textContent = 'לא נמצאו הקרנות מתוכננות';
      results.replaceChildren(message);
      return;
    }

    results.replaceChildren(
      ...visibleScreenings.map(scheduleItem)
    );
  } catch (error) {
    setStatus(error.message, true);
  }
}

function scheduleItem(screening) {
  const item = document.createElement('article');
  item.className = 'schedule-item';

  const title = document.createElement('strong');
  title.textContent = screening.movie_title;

  const details = document.createElement('span');
  details.textContent =
    `אולם ${screening.hall_id} · ` +
    `${scheduleDateFormat.format(new Date(screening.start_time))} · ` +
    `${screening.ticket_price} ₪`;

  item.append(title, details);
  return item;
}