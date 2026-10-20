# DO + WireGuard Manager

لوحة تحكم ويب + API لإدارة DigitalOcean Droplet + WireGuard + Reserved IP + Snapshots.

## الميزات
- عرض حالة Droplet + WireGuard + Reserved IP
- فحص تغيّر IP العام + تسجيله
- Snapshots تلقائية + تنظيف القديم
- تنبيهات (Telegram / بريد / Webhook)
- Watchdog لكشف توقف السيرفر
- واجهة HTML + HTMX (بدون تسجيل دخول — احمها بشبكة)

## التثبيت
```bash
make setup
nano .env          # DO_TOKEN
nano config.yaml   # droplet.id, region, interface
make run
