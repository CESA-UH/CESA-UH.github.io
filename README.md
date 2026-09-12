# cesa-uh.github.io

سایت مستندات گروه برق و کامپیوتر دانشگاه هرمزگان.

## افزودن محتوای یک درس

هر درس یک پوشه در `courses/<نام‌درس>/` دارد که شامل `index.html` و `data.json` است. برای افزودن محتوا فقط `data.json` را ویرایش کنید:

```json
{
  "schedule": [
    {
      "week": 1,
      "session": 1,
      "date": "2026-09-23",
      "title_fa": "مقدمه و مرور",
      "title_en": "Introduction & Review",
      "materials": [{ "title_fa": "اسلاید", "title_en": "Slides", "href": "slides/s1.pdf" }],
      "homework": { "title_fa": "تمرین ۱", "title_en": "Exercise 1", "href": "exercises/hw1.pdf" },
      "deadline": "2026-09-30"
    }
  ],
  "videos": [{ "title_fa": "جلسه ۱", "title_en": "Session 1", "src": "videos/session1.mp4" }],
  "notes": [{ "title_fa": "جزوه فصل ۱", "title_en": "Chapter 1 notes", "href": "notes/ch1.pdf" }],
  "exercises": [{ "title_fa": "تمرین ۱", "title_en": "Exercise 1", "href": "exercises/hw1.pdf" }],
  "code": [{ "title_fa": "کد جلسه ۱", "title_en": "Session 1 code", "href": "https://github.com/..." }]
}
```

`src` و `href` می‌توانند مسیر نسبی به فایلی در همان پوشه، یا لینک کامل (مثلاً لینک raw فایل mp4 آپلودشده در گیت‌هاب) باشند.

در `schedule`، `date` و `deadline` را همیشه به فرمت میلادی ساده `YYYY-MM-DD` بنویسید — سایت خودش آن‌ها را به تاریخ شمسی تبدیل و نمایش می‌دهد. `week` و `session` عدد هفته و شماره جلسه هستند (اختیاری؛ اگر ننویسید، شماره جلسه خودکار از روی ترتیب آرایه محاسبه می‌شود). `materials` آرایه‌ای از لینک‌هاست (اسلاید، جزوه و...) و `homework`/`deadline` اختیاری‌اند؛ هر فیلدی که برای یک جلسه لازم نیست را حذف کنید.

## افزودن یک درس جدید

1. پوشه‌ای مثل `courses/NEW/` بسازید و `index.html` یکی از دروس موجود را در آن کپی کنید (فقط عنوان‌ها را عوض کنید).
2. یک `data.json` خالی مثل بقیه دروس در همان پوشه بسازید.
3. یک رکورد جدید به `courses/index.json` اضافه کنید.
