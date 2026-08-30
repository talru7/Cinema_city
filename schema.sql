-- Cinema City - Cloudflare D1 schema
-- Version: 1
-- Target: Cloudflare D1 / SQLite
--
-- D1 enforces foreign keys. The schema deliberately keeps integrity rules
-- in the database as well as in the Python business layer.

CREATE TABLE IF NOT EXISTS cinemas (
    cinema_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    CHECK (length(trim(name)) > 0)
);

CREATE TABLE IF NOT EXISTS halls (
    hall_id INTEGER PRIMARY KEY,
    cinema_id INTEGER NOT NULL,
    hall_name TEXT NOT NULL UNIQUE,
    FOREIGN KEY (cinema_id)
        REFERENCES cinemas(cinema_id)
        ON UPDATE RESTRICT
        ON DELETE RESTRICT,
    CHECK (length(trim(hall_name)) > 0)
);

CREATE TABLE IF NOT EXISTS seats (
    seat_id INTEGER PRIMARY KEY,
    hall_id INTEGER NOT NULL,
    row_number INTEGER NOT NULL,
    seat_number INTEGER NOT NULL,
    FOREIGN KEY (hall_id)
        REFERENCES halls(hall_id)
        ON UPDATE RESTRICT
        ON DELETE RESTRICT,
    UNIQUE (hall_id, row_number, seat_number),
    CHECK (row_number > 0),
    CHECK (seat_number > 0)
);

CREATE TABLE IF NOT EXISTS movies (
    movie_id INTEGER PRIMARY KEY,
    title TEXT NOT NULL COLLATE NOCASE UNIQUE,
    duration_minutes INTEGER NOT NULL,
    description TEXT NOT NULL,
    genre TEXT NOT NULL,
    ticket_price INTEGER NOT NULL,
    CHECK (length(trim(title)) > 0),
    CHECK (duration_minutes BETWEEN 1 AND 240),
    CHECK (length(trim(description)) BETWEEN 1 AND 300),
    CHECK (genre IN ('comedy', 'drama', 'thriller', 'crime', 'family')),
    CHECK (ticket_price BETWEEN 1 AND 99)
);

CREATE TABLE IF NOT EXISTS movie_shows (
    show_id INTEGER PRIMARY KEY,
    movie_id INTEGER NOT NULL,
    hall_id INTEGER NOT NULL,
    start_time TEXT NOT NULL,
    ticket_price INTEGER NOT NULL,
    FOREIGN KEY (movie_id)
        REFERENCES movies(movie_id)
        ON UPDATE RESTRICT
        ON DELETE RESTRICT,
    FOREIGN KEY (hall_id)
        REFERENCES halls(hall_id)
        ON UPDATE RESTRICT
        ON DELETE RESTRICT,
    UNIQUE (show_id, hall_id),
    UNIQUE (hall_id, start_time),
    CHECK (length(trim(start_time)) > 0),
    CHECK (ticket_price BETWEEN 1 AND 99)
);

CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    auth_subject TEXT NOT NULL UNIQUE,
    full_name TEXT NOT NULL,
    phone_number TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL COLLATE NOCASE UNIQUE,
    CHECK (length(trim(auth_subject)) > 0),
    CHECK (length(trim(full_name)) >= 2),
    CHECK (length(trim(phone_number)) > 0),
    CHECK (length(trim(email)) > 0)
);

CREATE TABLE IF NOT EXISTS bookings (
    booking_id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    show_id INTEGER NOT NULL,
    FOREIGN KEY (user_id)
        REFERENCES users(user_id)
        ON UPDATE RESTRICT
        ON DELETE RESTRICT,
    FOREIGN KEY (show_id)
        REFERENCES movie_shows(show_id)
        ON UPDATE RESTRICT
        ON DELETE RESTRICT,
    UNIQUE (booking_id, show_id)
);

-- show_id is intentionally repeated in this junction table.
-- This enables a database-level UNIQUE(show_id, seat_id) constraint, so two
-- concurrent requests cannot reserve the same seat for the same show.
CREATE TABLE IF NOT EXISTS booking_seats (
    booking_id INTEGER NOT NULL,
    show_id INTEGER NOT NULL,
    seat_id INTEGER NOT NULL,
    PRIMARY KEY (booking_id, seat_id),
    FOREIGN KEY (booking_id, show_id)
        REFERENCES bookings(booking_id, show_id)
        ON UPDATE RESTRICT
        ON DELETE CASCADE,
    FOREIGN KEY (seat_id)
        REFERENCES seats(seat_id)
        ON UPDATE RESTRICT
        ON DELETE RESTRICT,
    UNIQUE (show_id, seat_id)
);

-- A booking may only contain seats that physically belong to the hall
-- in which its show is scheduled.
CREATE TRIGGER IF NOT EXISTS trg_booking_seat_must_match_show_hall
BEFORE INSERT ON booking_seats
FOR EACH ROW
WHEN (
    SELECT s.hall_id
    FROM seats AS s
    WHERE s.seat_id = NEW.seat_id
) <> (
    SELECT ms.hall_id
    FROM movie_shows AS ms
    WHERE ms.show_id = NEW.show_id
)
BEGIN
    SELECT RAISE(
        ABORT,
        'booking seat does not belong to the show hall'
    );
END;

CREATE INDEX IF NOT EXISTS idx_halls_cinema_id
    ON halls(cinema_id);

CREATE INDEX IF NOT EXISTS idx_seats_hall_id
    ON seats(hall_id);

CREATE INDEX IF NOT EXISTS idx_movie_shows_movie_id
    ON movie_shows(movie_id);

CREATE INDEX IF NOT EXISTS idx_bookings_user_id
    ON bookings(user_id);

CREATE INDEX IF NOT EXISTS idx_bookings_show_id
    ON bookings(show_id);

CREATE INDEX IF NOT EXISTS idx_booking_seats_booking_id
    ON booking_seats(booking_id);

CREATE INDEX IF NOT EXISTS idx_booking_seats_seat_id
    ON booking_seats(seat_id);
