# Deployment

## פרופיל מומלץ

```text
Browser
  -> HTTPS Gateway / Cloud Run
  -> FastAPI
  -> Clerk Authentication Adapter
  -> Application Services
  -> Neon Repositories
```

## Release

1. הגדירו Secrets ותצורת `.env.production` בפלטפורמת הענן.
2. הריצו `uv sync --frozen` ו-`bash scripts/check.sh`.
3. בנו image עם tag חד-חד-ערכי.
4. הריצו Job חד-פעמי `cinema-db-init` עם הרשאת DDL.
5. העלו את השרת עם `AUTO_CREATE_SCHEMA=false` ו-role ללא DDL.
6. בדקו `/api/health`, Login, הזמנה, ביטול ופעולת מנהל.
7. רק לאחר מכן העבירו תעבורה לגרסה החדשה.

## Cloud Run

ה-container מאזין ל-`0.0.0.0:${PORT}`. הגדירו:

```env
APP_ENV=production
HOST=0.0.0.0
PORT=8080
AUTH_ENABLED=true
AUTH_PROVIDER=clerk
STORAGE_BACKEND=neon
AUTO_CREATE_SCHEMA=false
```

הפעילו minimum instances רק אם זמן ה-Cold Start משמעותי. Connection pooling מוגדר עם `pool_pre_ping`; יש לכוון את מגבלת החיבורים לפי מגבלת Neon ומספר ה-instances.

## Gateway יחיד או שניים

למערכת קטנה מומלץ להתחיל ב-`API_MODE=combined`. אם נדרשים isolation, הרשאות deployment או rate limits שונים, פרסו שני containers מאותו image:

```text
customer-api -> API_MODE=customer
manager-api  -> API_MODE=manager
```

אין לשנות Business Logic בין שני ה-deployments.

## Rollback

Rollback של image אינו Rollback של schema. שינויי schema עתידיים חייבים להיות backward-compatible לפחות לגרסה אחת, עם Migration קדימה נפרד ותכנית Restore מתועדת.
