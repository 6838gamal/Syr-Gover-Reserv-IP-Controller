SHELL := /bin/bash
VENV  := .venv
PY    := $(VENV)/bin/python
PIP   := $(VENV)/bin/pip
APP   := app.main:app
HOST  := 127.0.0.1
PORT  := 8000

.DEFAULT_GOAL := help

.PHONY: help
help:
	@echo "الأوامر:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; \
	         {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

.PHONY: venv
venv: ## إنشاء بيئة Python
	python3 -m venv $(VENV)

.PHONY: install
install: venv ## تثبيت الاعتماديات
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

.PHONY: env
env: ## إنشاء .env
	@if [ ! -f .env ]; then \
	  cp .env.example .env; chmod 600 .env; \
	  echo "✅ .env أُنشئ"; \
	else echo "ℹ️ .env موجود"; fi

.PHONY: htmx
htmx: ## تنزيل htmx
	@if [ ! -f app/static/htmx.min.js ]; then \
	  curl -sL -o app/static/htmx.min.js \
	    https://unpkg.com/htmx.org@1.9.12/dist/htmx.min.js; \
	  echo "✅ htmx نُزّل"; \
	else echo "ℹ️ htmx موجود"; fi

.PHONY: setup
setup: install env htmx ## إعداد كامل
	@echo "✅ جاهز. عدّل .env ثم: make run"

.PHONY: run
run: ## تشغيل تطوير
	$(VENV)/bin/uvicorn $(APP) --host $(HOST) --port $(PORT) --reload

.PHONY: run-prod
run-prod: ## تشغيل إنتاج
	$(VENV)/bin/uvicorn $(APP) --host $(HOST) --port $(PORT) --workers 2

.PHONY: check
check: ## فحص health
	@curl -s http://$(HOST):$(PORT)/health; echo

.PHONY: install-service
install-service: ## تثبيت systemd
	sudo tee /etc/systemd/system/do-wg-api.service > /dev/null <<'EOF'
[Unit]
Description=DO + WireGuard Manager API
After=network-online.target

[Service]
Type=simple
WorkingDirectory=$(CURDIR)
EnvironmentFile=$(CURDIR)/.env
ExecStart=$(CURDIR)/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=10
User=root

[Install]
WantedBy=multi-user.target
EOF
	sudo systemctl daemon-reload
	sudo systemctl enable --now do-wg-api
	@echo "✅ خدمة مثبتة"

.PHONY: restart
restart: ## إعادة تشغيل الخدمة
	sudo systemctl restart do-wg-api

.PHONY: logs
logs: ## متابعة السجلات
	sudo journalctl -u do-wg-api -f

.PHONY: secure
secure: ## إغلاق المنفذ
	@sudo ufw deny $(PORT) 2>/dev/null || true
	@echo "✅ مغلق. SSH tunnel:"
	@echo "  ssh -L $(PORT):127.0.0.1:$(PORT) root@VPS"

.PHONY: compose-up
compose-up: ## docker compose up
	docker compose up -d --build

.PHONY: compose-down
compose-down: ## docker compose down
	docker compose down

.PHONY: clean
clean: ## تنظيف
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache 2>/dev/null || true
