#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/do-wg-api}"
SERVICE_NAME="do-wg-api"
PYTHON_BIN="${PYTHON_BIN:-python3}"
PORT="${PORT:-8000}"
REPO_URL="${REPO_URL:-}"
TARBALL="${TARBALL:-}"

RED=$'\033[31m'; GRN=$'\033[32m'; YEL=$'\033[33m'; CYN=$'\033[36m'; RST=$'\033[0m'
log(){ echo "${CYN}▶${RST} $*"; }
ok(){ echo "${GRN}✅${RST} $*"; }
warn(){ echo "${YEL}⚠️ ${RST} $*"; }
err(){ echo "${RED}❌${RST} $*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || err "شغّل كـ root أو sudo"

for cmd in curl tar systemctl ufw; do
  command -v "$cmd" >/dev/null || err "مفقود: $cmd"
done
command -v "$PYTHON_BIN" >/dev/null || err "مفقود: $PYTHON_BIN"

if ! "$PYTHON_BIN" -c 'import venv' 2>/dev/null; then
  apt-get update -qq
  apt-get install -y -qq python3-venv python3-pip
fi

if [[ -n "$TARBALL" ]]; then
  mkdir -p "$APP_DIR"
  tar -xzf "$TARBALL" -C "$APP_DIR" --strip-components=1
elif [[ -n "$REPO_URL" ]]; then
  if [[ -d "$APP_DIR/.git" ]]; then
    git -C "$APP_DIR" pull --ff-only
  else
    mkdir -p "$(dirname "$APP_DIR")"
    git clone "$REPO_URL" "$APP_DIR"
  fi
elif [[ ! -d "$APP_DIR" ]]; then
  err "لا مصدر كود. مرّر REPO_URL/TARBALL"
fi

cd "$APP_DIR"

if [[ ! -f .env ]]; then
  cp .env.example .env
  chmod 600 .env
  warn ".env أُنشئ — حرّره ثم أعد التشغيل:"
  echo "    nano $APP_DIR/.env"
  exit 0
fi

grep -q '^DO_TOKEN=.\+' .env || err "DO_TOKEN فارغ"

[[ -d .venv ]] || "$PYTHON_BIN" -m venv .venv
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements.txt
ok "الاعتماديات مثبتة"

if [[ ! -f app/static/htmx.min.js ]]; then
  curl -sL -o app/static/htmx.min.js \
    https://unpkg.com/htmx.org@1.9.12/dist/htmx.min.js
fi

mkdir -p /var/lib/do-wg && chmod 700 /var/lib/do-wg

cat > "/etc/systemd/system/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=DO + WireGuard Manager API
After=network-online.target

[Service]
Type=simple
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
ExecStart=${APP_DIR}/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port ${PORT}
Restart=always
RestartSec=10
User=root

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now "$SERVICE_NAME"
ok "الخدمة تعمل"

for i in {1..20}; do
  if curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
    ok "التطبيق يستجيب"; break
  fi
  sleep 1
  [[ $i -eq 20 ]] && err "لا استجابة — راجع: journalctl -u $SERVICE_NAME -n 50"
done

ufw deny "$PORT" >/dev/null 2>&1 || warn "ufw غير مفعّل"

PUBLIC_IP=$(curl -s --max-time 5 https://api.ipify.org || echo "VPS_IP")
echo
ok "اكتمل النشر"
echo "  الخدمة:  systemctl status $SERVICE_NAME"
echo "  السجلات: journalctl -u $SERVICE_NAME -f"
echo "  الواجهة: ssh -L $PORT:127.0.0.1:$PORT root@$PUBLIC_IP"
echo "           ثم http://localhost:$PORT"
