# Security

## מודל אמון

הדפדפן אינו מקור סמכות. השרת אינו מקבל ממנו `user_id`, תפקיד, הרשאות או כתובת דוא"ל לצורך Authorization.

## Clerk JWT

`ClerkJwtVerifier` מאמת:

- חתימת RS256 מול JWKS
- `iss`
- `exp`
- `iat`
- `nbf`
- `sub`
- `azp` מול `CLERK_AUTHORIZED_PARTIES`

אחרי אימות הטוקן, נתוני הפרופיל וסטטוס אימות הדוא"ל נקראים מ-Clerk Backend API. רק דוא"ל ראשי ומאומת יכול להעניק תפקיד מנהל.

## Authorization

כל endpoint מוגן דורש `AuthContext`. נתיבי מנהל דורשים בנוסף `Role.MANAGER` והרשאה ייעודית. הסתרת כפתור ב-JavaScript היא שיפור UX בלבד.

## Secrets

- אין להכניס `.env.local` או `.env.production` ל-Git.
- `CLERK_SECRET_KEY`, טוקן D1 וחיבור Neon נשמרים ב-Secret Manager.
- `CLERK_PUBLISHABLE_KEY` הוא הערך היחיד של Clerk שמותר להעביר לדפדפן.
- מומלץ להשתמש ב-role נפרד ל-Migration וב-role מצומצם לשרת.

## HTTP

השרת מוסיף `nosniff`, הגנת iframe, Referrer Policy, Permissions Policy, Request ID ו-`no-store` לתשובות API. יש להפעיל TLS ב-Gateway ולצמצם `ALLOWED_HOSTS` ו-`CORS_ORIGINS` ל-domains המדויקים.

## שגיאות

שגיאות Business מוחזרות כ-400, הזדהות כ-401, הרשאה כ-403 ואחסון כ-503 ללא פרטים פנימיים. שגיאות בלתי צפויות אינן נבלעות.

## לפני Production

- להחליף את כתובות הדוגמה.
- להפעיל TLS ו-HSTS ב-Gateway.
- להגדיר rate limits חיצוניים לנתיבי Login ו-Booking.
- לחבר structured logs, metrics והתראות.
- להריץ Dependency ו-Container scanning בצינור הארגוני.
- לבדוק Restore מגיבוי Neon לפני פתיחה ללקוחות.
