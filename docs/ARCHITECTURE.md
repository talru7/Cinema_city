# Architecture

## גבולות המערכת

מודלי ה-Domain מכילים ערכים ומזהים בלבד. יצירה חדשה מיוצגת באמצעות אותו Entity עם מזהה `None`; ה-Repository מקצה מזהה ומחזיר ID בלבד.

החוזים המרכזיים הם:

- `CinemaConfigRepository`
- `MovieRepository`
- `ShowRepository`
- `UserRepository`
- `BookingRepository`
- `AuthenticationService`

`StorageService` הוא Facade לקריאות משולבות. הוא אינו בוחר implementation ואינו קורא ENV.

## Composition Root

רק `cinema/composition.py` רשאי לבחור implementations לפי `Settings`:

```text
STORAGE_BACKEND=json  -> Json repositories
STORAGE_BACKEND=neon -> SQLAlchemy/PostgreSQL repositories

AUTH_PROVIDER=none   -> NoAuthAuthenticationService
AUTH_PROVIDER=clerk  -> ClerkAuthenticationService
```

D1 ו-MongoDB הם ערכי Configuration שמורים. בחירה בהם נכשלת מיד עם הודעה ברורה עד שקיים adapter שעובר את בדיקות החוזה.

## זהות

```text
External token
  -> AuthenticationService
  -> (provider, subject)
  -> UserRepository
  -> local user_id
  -> AuthContext
  -> Application Service
```

ה-Business Logic מקבל `user_id`, תפקיד והרשאות בלבד. הוא אינו מקבל Clerk ID או JWT.

## הזמנה אטומית

ב-JSON, בדיקת זמינות וכתיבת `booking + booking_seats` מתבצעות תחת אותה נעילת קובץ.

ב-Neon, שתי הפעולות מתבצעות ב-transaction אחד. `booking_seats` שומר במפורש `show_id` ומוגן באמצעות:

```sql
UNIQUE (show_id, seat_id)
```

לכן שתי בקשות מקבילות לא יכולות להזמין את אותו מושב לאותה הקרנה, גם אם שתיהן עברו בדיקת Application מוקדמת.

## תזמון

`SchedulingService` הוא Stateless. בכל פעולה הוא טוען snapshot מה-Repositories, בודק overlap ומוסיף 20 דקות ניקיון בין הקרנות. אין בו `self.shows` או מונה מזהים.

## Gateways

`API_MODE` קובע אילו routers נחשפים:

- `combined` - Public, Customer ו-Manager באותו deployment
- `customer` - Public ו-Customer בלבד
- `manager` - Public ו-Manager בלבד

כל המצבים משתמשים באותם Application Services. הפרדה לשני domains היא החלטת Deployment בלבד.
