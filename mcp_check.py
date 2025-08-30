#!/usr/bin/env python3
"""
MCP Streamable HTTP Checker для Telegram Toolkit MCP
Проверяет полный MCP протокол с нашими инструментами
"""

import argparse
import json
import sys
import time
from typing import Optional, Dict, Any
import requests


DEFAULT_PROTO = "2025-06-18"


def first_sse_json(resp: requests.Response) -> Optional[Dict[str, Any]]:
    """
    Возвращает первый JSON-объект из SSE потока (строки, начинающиеся с 'data: ').
    Если ответ application/json — вернёт resp.json().
    """
    ctype = (resp.headers.get("Content-Type") or "").lower()
    if "text/event-stream" in ctype:
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            # Возможны кадры 'event: ...', 'id: ...', 'retry: ...'
            if line.startswith("data:"):
                payload = line[5:].strip()
                if payload:
                    return json.loads(payload)
        return None
    # fallback — обычный JSON
    return resp.json() if resp.content else None


class MCPChecker:
    """MCP Streamable HTTP Checker для нашего сервера"""

    def __init__(self, base_url: str, proto: str = DEFAULT_PROTO, timeout: int = 60, debug: bool = False):
        self.base_url = base_url.rstrip("/")  # .../mcp
        self.proto = proto
        self.sess = requests.Session()
        self.sid: Optional[str] = None
        self.timeout = timeout
        self.debug = debug

    def _headers(self, with_sid: bool = True) -> Dict[str, str]:
        """Формирует заголовки для MCP запросов"""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": self.proto,
        }
        if with_sid and self.sid:
            headers["Mcp-Session-Id"] = self.sid
        return headers

    def initialize(self, client_name: str = "mcp-checker", client_version: str = "0.1") -> Optional[Dict[str, Any]]:
        """Инициализация MCP сессии"""
        payload = {
            "jsonrpc": "2.0",
            "id": 0,
            "method": "initialize",
            "params": {
                "protocolVersion": self.proto,
                "capabilities": {"tools": {}},
                "clientInfo": {"name": client_name, "version": client_version},
            },
        }

        print("📡 Отправка initialize..." if self.debug else "", end="", flush=True)

        resp = self.sess.post(
            self.base_url, json=payload, headers=self._headers(with_sid=False),
            timeout=self.timeout, stream=True
        )
        resp.raise_for_status()

        # SID приходит в заголовке ответа
        sid = resp.headers.get("Mcp-Session-Id") or resp.headers.get("mcp-session-id")
        if not sid:
            print("⚠️  Warning: initialize ок, но сервер не вернул Mcp-Session-Id", file=sys.stderr)
        else:
            self.sid = sid.strip()

        result = first_sse_json(resp)
        if self.debug:
            print("INIT headers:", dict(resp.headers), file=sys.stderr)
            print("INIT body:", result, file=sys.stderr)

        return result

    def notify_initialized(self) -> int:
        """Отправка notifications/initialized"""
        payload = {"jsonrpc": "2.0", "method": "notifications/initialized"}

        print("📡 Отправка notifications/initialized..." if self.debug else "", end="", flush=True)

        resp = self.sess.post(
            self.base_url, json=payload, headers=self._headers(),
            timeout=self.timeout, stream=True
        )

        if self.debug:
            print(f"NOTIFY status: {resp.status_code}", file=sys.stderr)

        return resp.status_code

    def rpc(self, method: str, params: Optional[Dict[str, Any]] = None, rid: int = 1) -> Optional[Dict[str, Any]]:
        """Отправка JSON-RPC запроса"""
        payload = {"jsonrpc": "2.0", "id": rid, "method": method}
        if params is not None:
            payload["params"] = params

        print(f"📡 RPC {method}..." if self.debug else "", end="", flush=True)

        resp = self.sess.post(
            self.base_url, json=payload, headers=self._headers(),
            timeout=self.timeout, stream=True
        )
        resp.raise_for_status()

        data = first_sse_json(resp)
        if self.debug:
            print(f"RPC {method} → {data}", file=sys.stderr)

        return data

    def tools_list(self) -> Optional[Dict[str, Any]]:
        """Получение списка инструментов"""
        try:
            # Сначала пробуем без params
            return self.rpc("tools/list", rid=2)
        except requests.HTTPError:
            # Если не сработало, пробуем с пустыми params
            return self.rpc("tools/list", params={}, rid=2)

    def call_tool(self, name: str, arguments: Dict[str, Any], rid: int = 3) -> Optional[Dict[str, Any]]:
        """Вызов инструмента"""
        return self.rpc("tools/call", {"name": name, "arguments": arguments}, rid=rid)


def main():
    """Основная функция проверки"""
    ap = argparse.ArgumentParser(description="MCP Streamable HTTP checker для Telegram Toolkit")
    ap.add_argument("--domain", default="tgtoolkit.azazazaza.work", help="Домен MCP сервера")
    ap.add_argument("--scheme", default="https", choices=["http", "https"])
    ap.add_argument("--path", default="/mcp", help="Путь эндпойнта (по умолчанию /mcp)")
    ap.add_argument("--proto", default=DEFAULT_PROTO, help="MCP-Protocol-Version")
    ap.add_argument("--chat", default="@telegram", help="Чат для тестового вызова")
    ap.add_argument("--timeout", type=int, default=60, help="Таймаут запросов")
    ap.add_argument("--debug", action="store_true", help="Режим отладки")
    ap.add_argument("--call", choices=["none", "resolve", "fetch"], default="resolve",
                    help="Какой tools/call выполнить после tools/list")
    args = ap.parse_args()

    base_url = f"{args.scheme}://{args.domain}{args.path}"
    print(f"🚀 MCP Checker для: {base_url}")
    print("=" * 60)

    chk = MCPChecker(base_url, proto=args.proto, timeout=args.timeout, debug=args.debug)

    # 1. Initialize
    print("1️⃣  Initialize...")
    start_time = time.time()
    init = chk.initialize()
    init_time = time.time() - start_time

    if not chk.sid:
        print("❌ Нет Mcp-Session-Id — сервер работает некорректно")
        sys.exit(2)

    print(f"   ✅ SID: {chk.sid}")
    print(f"   ⏱️  Initialize time: {init_time:.2f}s")
    print(f"   📋 Server info: {init.get('result', {}).get('serverInfo', {}) if init else 'N/A'}")

    # 2. Notifications
    print("\n2️⃣  Notifications/initialized...")
    start_time = time.time()
    code = chk.notify_initialized()
    notify_time = time.time() - start_time

    if code in [200, 202, 204]:
        print(f"   ⏱️  Notifications time: {notify_time:.2f}s")
    else:
        print(f"   ⚠️  Неожиданный статус: {code}")

    # 3. Tools list
    print("\n3️⃣  Tools/list...")
    start_time = time.time()
    tlist = chk.tools_list()
    list_time = time.time() - start_time

    if tlist and "result" in tlist:
        tools = tlist["result"].get("tools", [])
        print(f"   ✅ Найдено инструментов: {len(tools)}")
        for i, tool in enumerate(tools, 1):
            print(f"      {i}. {tool.get('name', 'Unknown')}")
            if args.debug:
                print(f"         📝 {tool.get('description', 'No description')[:100]}...")
    else:
        print("   ❌ Не удалось получить список инструментов")
        if tlist:
            print(f"   📋 Ответ: {tlist}")

    # 4. Tool call (опционально)
    if args.call != "none" and tlist:
        print(f"\n4️⃣  Tools/call: {args.call}...")

        if args.call == "resolve":
            print(f"   🎯 Тестируем resolve_chat_tool с чатом: {args.chat}")
            start_time = time.time()
            res = chk.call_tool("resolve_chat_tool", {"input": args.chat}, rid=10)
            call_time = time.time() - start_time

            if res and "result" in res:
                print(f"   ⏱️  Tool call time: {call_time:.2f}s")
                if args.debug:
                    print(f"   📋 Результат: {json.dumps(res['result'], ensure_ascii=False, indent=2)}")
            else:
                print("   ❌ Ошибка вызова resolve_chat_tool")
                if res and "error" in res:
                    print(f"   📋 Ошибка: {res['error']}")

        elif args.call == "fetch":
            print(f"   🎯 Тестируем fetch_history_tool с чатом: {args.chat}")
            start_time = time.time()
            res = chk.call_tool("fetch_history_tool", {"chat_id": args.chat, "limit": 3}, rid=11)
            call_time = time.time() - start_time

            if res and "result" in res:
                messages = res["result"].get("messages", [])
                print(f"   ⏱️  Tool call time: {call_time:.2f}s")
                if args.debug:
                    print(f"   📋 Сообщения: {len(messages)}")
                    for msg in messages[:2]:  # Покажем первые 2
                        print(f"      • {msg.get('text', 'N/A')[:50]}...")
            else:
                print("   ❌ Ошибка вызова fetch_history_tool")
                if res and "error" in res:
                    print(f"   📋 Ошибка: {res['error']}")
    else:
        call_time = 0

    # Итоговая статистика
    print("\n" + "=" * 60)
    print("📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ:")
    print("=" * 60)
    print(f"   ⏱️  Initialize: {init_time:.2f}s")
    print(f"   ⏱️  Notifications: {notify_time:.2f}s")
    print(f"   ⏱️  Tools list: {list_time:.2f}s")
    if args.call != "none":
        print(f"   ⏱️  Tool call: {call_time:.2f}s")

    print("
📋 Инструменты:"
    if tlist and "result" in tlist:
        tools = tlist["result"].get("tools", [])
        print(f"   ✅ Найдено: {len(tools)}")
        for tool in tools:
            name = tool.get('name', 'Unknown')
            print(f"      • {name}")
    else:
        print("   ❌ Не получены")

    print("
🎯 СТАТУС:"
    success = (
        chk.sid is not None and
        code in [200, 202, 204] and
        (tlist is not None and "result" in tlist)
    )

    if success:
        print("   ✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
        print("   🎉 MCP сервер работает корректно")
    else:
        print("   ❌ Некоторые тесты не пройдены")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except requests.HTTPError as e:
        # Печатаем тело ответа для удобной отладки
        if e.response is not None:
            sys.stderr.write(f"\nHTTPError {e.response.status_code}: {e.response.text}\n")
        raise
    except KeyboardInterrupt:
        print("\n❌ Прервано пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        if "--debug" in sys.argv:
            import traceback
            traceback.print_exc()
        sys.exit(1)
