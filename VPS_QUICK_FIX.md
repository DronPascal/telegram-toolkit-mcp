# 🚀 VPS Quick Fix - Решение проблем с установкой

## Проблема: Ошибки с правами доступа и venv

```bash
# Ошибка 1: ensurepip is not available
python3 -m venv ~/mcp_verifier
# The virtual environment was not created successfully because ensurepip is not available

# Ошибка 2: Permission denied
apt install python3.12-venv
# E: Could not open lock file /var/lib/dpkg/lock-frontend - open (13: Permission denied)
```

## ✅ РЕШЕНИЕ: Используйте системный пакет (самый простой способ)

```bash
# Установить httpx через системный пакет менеджер
sudo apt update && sudo apt install python3-httpx

# Запустить проверку
python3 scripts/validation/verify_vps_deployment.py https://your-domain.com
```

## 🔧 Альтернативное решение: Виртуальное окружение

```bash
# 1. Установить пакет venv с sudo
sudo apt install python3.12-venv

# 2. Создать виртуальное окружение
python3 -m venv ~/mcp_verifier

# 3. Установить httpx в виртуальное окружение
~/mcp_verifier/bin/pip install httpx

# 4. Запустить проверку через виртуальное окружение
~/mcp_verifier/bin/python3 scripts/validation/verify_vps_deployment.py https://your-domain.com
```

## 🎯 Рекомендуемая последовательность команд для VPS:

```bash
# 1. Развернуть исправления сервера
cd /opt/telegram-toolkit-mcp
git pull origin main
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# 2. Установить httpx (системный пакет - проще всего)
sudo apt update && sudo apt install python3-httpx

# 3. Запустить проверку
python3 scripts/validation/verify_vps_deployment.py https://your-domain.com
```

## 📊 Ожидаемый результат:

```
🚀 VPS Deployment Verification
🎯 Target: https://your-domain.com

✅ PASS HTTP Connectivity
✅ PASS Health Check
✅ PASS Metrics Endpoint
✅ PASS Debug Headers
✅ PASS MCP Session Creation
✅ PASS MCP Initialize Response
✅ PASS MCP Tools List
✅ PASS MCP Tool Call

📊 Results: 7/7 tests passed (100.0%)
🎉 ALL TESTS PASSED - VPS deployment is fully operational!
```

## 💡 Если все еще есть проблемы:

### 🔍 Быстрая диагностика:
```bash
# Запустить полную диагностику сервера
./scripts/validation/diagnose_vps.sh
```

### 🔧 Ручная проверка:

1. **Проверить статус контейнера:**
   ```bash
   docker-compose ps
   docker logs telegram-toolkit-mcp
   ```

2. **Убедиться что исправления применены:**
   ```bash
   git log --oneline -3
   # Должен быть коммит с "fix: resolve critical FastMCP server TypeError issues"
   ```

3. **Проверить локальные endpoints:**
   ```bash
   curl http://localhost:8000/health
   curl http://localhost:8000/metrics | head -5
   ```

4. **Если endpoints не работают локально:**
   ```bash
   docker-compose build --no-cache
   docker-compose up -d
   ```

### ⚠️ Важно: Используйте РЕАЛЬНЫЙ домен!

```bash
# ❌ НЕПРАВИЛЬНО (placeholder):
python3 scripts/validation/verify_vps_deployment.py https://your-domain.com

# ✅ ПРАВИЛЬНО (ваш реальный домен):
python3 scripts/validation/verify_vps_deployment.py https://your-real-domain.com

# ✅ Или локально для тестирования:
python3 scripts/validation/verify_vps_deployment.py http://localhost:8000
```

