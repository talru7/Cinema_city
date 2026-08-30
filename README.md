# Cinema City

Current version: **9.7.2**

Production-style Python teaching project for cinema scheduling, booking,
repository abstractions, persistence, testing, and future Cloudflare D1 integration.

הפרויקט כולל:

- שני ממשקי CLI נפרדים ללקוחות ולמנהלים
- ממשק Web רספונסיבי ב-HTML, CSS ו-JavaScript נקיים
- FastAPI עם API ציבורי, API מוגן ללקוחות ו-API מוגן למנהלים
- `NoAuthAuthenticationService` מפורש לפיתוח מקומי ללא אינטרנט
- `ClerkAuthenticationService` עם אימות JWT בצד השרת ומיפוי ל-`user_id` פנימי
- JSON מקומי עם `filelock`, כתיבה אטומית ונתיבי `platformdirs`
- PostgreSQL/Neon עם Foreign Keys, Check Constraints והגנת DB מפני הזמנה כפולה
- Composition Root יחיד לבחירת Authentication, Storage ו-Gateway
- 109 בדיקות Unit, Integration ו-Repository Contract עם כיסוי של לפחות 90%

## התחלה מהירה

נדרשים Python 3.12 ו-[uv](https://docs.astral.sh/uv/).

```bash
uv sync --frozen
cp .env.local.example .env.local
uv run cinema-web
```

פתחו:

```text
http://127.0.0.1:8000
http://127.0.0.1:8000/manager
```

ב-Windows העתיקו את `.env.local.example` ידנית ל-`.env.local` או השתמשו ב-PowerShell:

```powershell
Copy-Item .env.local.example .env.local
uv run cinema-web
```

מצב `NoAuth` הוא adapter מקומי אמיתי. תפקיד הלקוח או המנהל נקבע לפי קבוצת ה-routes בשרת ולא מתקבל מהדפדפן.

## פקודות הפעלה

```bash
# CLI
uv run cinema-customer
uv run cinema-manager

# Gateway משולב
uv run cinema-web

# שני Gateways נפרדים מאותו קוד
uv run cinema-customer-web
uv run cinema-manager-web
```

ניתן לבחור גם באמצעות:

```env
API_MODE=combined
# API_MODE=customer
# API_MODE=manager
```

## מבנה הפרויקט

```text
src/cinema/
├── application/       # תרחישי שימוש ו-DTO לקריאה
├── auth/              # AuthContext, NoAuth ו-Clerk
├── cli/               # מתאמי CLI
├── config/            # Settings מרוכזים
├── exceptions/        # שגיאות Domain/Application מפורשות
├── models/            # ישויות עסקיות בלבד
├── services/          # חוקי הזמנה, תזמון וניהול
├── storage/           # Interfaces, JSON ו-Neon
├── web/               # FastAPI ונכסי Vanilla Web
├── composition.py     # Composition Root יחיד
└── db_init.py         # אתחול DB מפורש לפריסה
```

כיוון התלות:

```text
Web / CLI
    -> Application Services
        -> Business Services
            -> Repository Interfaces
                <- JSON / Neon Adapters
```

הליבה אינה מייבאת FastAPI, Clerk, SQLAlchemy, JSON או HTML.

## הזדהות והרשאות

ה-Frontend שולח רק:

```http
Authorization: Bearer <Clerk session token>
```

השרת:

1. מאמת חתימה, `exp`, `iat`, `nbf`, `iss` ו-`azp`.
2. קורא מ-Clerk את כתובת הדוא"ל הראשית ואת מצב האימות שלה.
3. ממפה `(auth_provider, auth_subject)` למשתמש המקומי.
4. יוצר `AuthContext(user_id, role, permissions)` פנימי.
5. בודק Authorization לפני קריאה לשירות העסקי.

`Clerk user ID` אינו משמש כמפתח עסקי. הזמנות וקשרים נשמרים רק מול `user_id` פנימי.

מנהלים מוגדרים כרגע באמצעות רשימת כתובות דוא"ל מאומתות:

```env
MANAGER_EMAILS=admin@example.com,manager@example.com
```

## Storage

### JSON מקומי

```env
STORAGE_BACKEND=json
CINEMA_DATA_DIR=./runtime-data
```

קבצי schema v3:

```text
cinema_config.json
movies.json
shows.json
users.json
bookings.json
```

פעולות read-modify-write מוגנות בנעילה, נכתבות לקובץ זמני, עוברות `fsync` ומוחלפות באמצעות `os.replace()`.

### Neon

```env
STORAGE_BACKEND=neon
NEON_DATABASE_URL=postgresql://...
AUTO_CREATE_SCHEMA=false
```

לפני העלאת שרת חדש מריצים פעם אחת כחלק מתהליך ה-Release:

```bash
uv run cinema-db-init
```

השרת עצמו אינו מקבל כברירת מחדל הרשאת DDL. במסד הנתונים נאכפים PK, FK, טווחים, זהות חיצונית ייחודית ו-`UNIQUE(show_id, seat_id)`.

### D1 ו-MongoDB

ה-Settings וה-Composition Root מכירים את השמות `d1` ו-`mongodb`, אך adapters אלה אינם מוצגים כמוכנים לייצור ללא בדיקות אינטגרציה מול שירותים אמיתיים. הוספתם אינה דורשת שינוי ב-Business Logic - מממשים את אותם Repository Contracts ומריצים את בדיקות החוזה הקיימות.

## Clerk בענן

העתיקו את `.env.production.example` והשלימו את הערכים מתוך Clerk:

```env
APP_ENV=production
AUTH_ENABLED=true
AUTH_PROVIDER=clerk
CLERK_PUBLISHABLE_KEY=pk_...
CLERK_SECRET_KEY=sk_...
CLERK_ISSUER=https://...
CLERK_JWKS_URL=https://.../.well-known/jwks.json
CLERK_FRONTEND_API_URL=https://...
CLERK_AUTHORIZED_PARTIES=https://cinema.example.com
```

ה-Secret Key נשמר בשרת או ב-Secret Manager בלבד. הוא אינו נכתב ב-HTML, ב-JavaScript, ב-Git או ב-GitHub Pages.

## API עיקרי

Public:

```text
GET  /api/health
GET  /api/config
GET  /api/movies
GET  /api/shows
GET  /api/shows/{show_id}/seats
```

Customer protected:

```text
POST   /api/customer/bookings
GET    /api/customer/bookings
DELETE /api/customer/bookings/{booking_id}
```

Manager protected:

```text
POST /api/manager/movies
POST /api/manager/shows
GET  /api/manager/bookings
GET  /api/manager/report
```

במצב שאינו Production זמין OpenAPI ב-`/api/docs`.

## בדיקות ואיכות

```bash
bash scripts/check.sh
```

או ב-Windows:

```bat
scripts\check.bat
```

הבדיקה המלאה מריצה לפי הסדר:

```text
pytest + coverage >= 90%
ruff check
mypy strict
pylint >= 9.0
ruff format --check
```

בדיקות החוזה רצות מול JSON ומול SQLAlchemy/SQLite, המייצג את אותם adapters של PostgreSQL/Neon ללא תלות בשירות חיצוני ב-CI.

## Docker

```bash
docker build -t cinema-city:10.0.0 .
docker run --rm -p 8080:8080 --env-file .env.production cinema-city:10.0.0
```

לפריסה מלאה והקשחת אבטחה ראו:

- [Architecture](docs/ARCHITECTURE.md)
- [Security](docs/SECURITY.md)
- [Deployment](docs/DEPLOYMENT.md)

## החלטות הרחבה

המערכת מוכנה להוספת ספק Auth נוסף או Storage נוסף באמצעות adapter חדש בלבד. תשלומים, מנויים, קופונים, Audit Log והתראות לא מומשו, אך המזהה הפנימי והגבולות הקיימים מאפשרים להוסיף אותם בלי לקשור את המוצר ל-Clerk או ל-Neon.
