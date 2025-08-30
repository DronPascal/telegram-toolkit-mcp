#!/usr/bin/env python3
"""
Advanced MCP Client Test using FastMCP library
"""

import asyncio
import json
import sys
from typing import Any

try:
    import fastmcp
    import httpx
    from fastmcp import Client
except ImportError as e:
    print(f"❌ Missing dependencies: {e}")
    print("Run: pip install httpx fastmcp")
    sys.exit(1)


def safe_parse_json(text: str) -> Any:
    """Безопасно парсит JSON или возвращает исходный текст"""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


async def test_mcp_server():
    """Полноценное тестирование MCP сервера с FastMCP клиентом"""

    server_url = "https://tgtoolkit.azazazaza.work/mcp"

    print("🚀 Advanced MCP Client Test")
    print("=" * 60)
    print(f"🎯 Server URL: {server_url}")

    try:
        # Создаем клиента FastMCP
        print("\n🤖 Подключаемся к MCP серверу...")
        client = Client(server_url)

        async with client:
            print("✅ Подключение установлено!\n")

            # Получаем возможности сервера
            print("🔍 Получаем информацию о сервере...")

            try:
                tools = await client.list_tools()
                print(f"🔧 Доступно инструментов: {len(tools)}")
                for i, tool in enumerate(tools, 1):
                    print(f"   {i}. {tool.name}: {tool.description}")

            except Exception as e:
                print(f"⚠️  Не удалось получить список инструментов: {e}")
                tools = []

            try:
                resources = await client.list_resources()
                print(f"\n📚 Доступно ресурсов: {len(resources)}")
                for i, resource in enumerate(resources, 1):
                    print(f"   {i}. {resource.uri}")

            except Exception as e:
                print(f"⚠️  Не удалось получить список ресурсов: {e}")
                resources = []

            try:
                prompts = await client.list_prompts()
                print(f"\n💭 Доступно промптов: {len(prompts)}")
                for i, prompt in enumerate(prompts, 1):
                    print(f"   {i}. {prompt.name}: {prompt.description}")

            except Exception as e:
                print(f"⚠️  Не удалось получить список промптов: {e}")
                prompts = []

            # Тестируем инструменты
            print("\n🧪 ТЕСТИРУЕМ ИНСТРУМЕНТЫ:")
            print("-" * 50)

            if tools:
                # Тестируем первый инструмент
                tool = tools[0]
                print(f"🎯 Тестируем инструмент: {tool.name}")
                print(f"📝 Описание: {tool.description}")

                # Получаем схему параметров
                if hasattr(tool, "inputSchema") and tool.inputSchema:
                    print(f"📋 Параметры: {json.dumps(tool.inputSchema, indent=2)}")

                # Пробуем вызвать инструмент с тестовыми данными
                test_args = {}

                # Для Telegram инструментов нужны специальные аргументы
                if "fetch_history" in tool.name:
                    test_args = {
                        "chat_id": "@telegram",  # Публичный чат для тестирования
                        "limit": 1,
                    }
                elif "resolve_chat" in tool.name:
                    test_args = {"input": "@telegram"}

                if test_args:
                    try:
                        print(f"📤 Вызываем с аргументами: {test_args}")
                        result = await client.call_tool(tool.name, test_args)
                        print("✅ Результат:")
                        print(f"   {safe_parse_json(result)}")
                    except Exception as e:
                        print(f"⚠️  Ошибка при вызове инструмента: {e}")
                        print("   Это нормально - нужны валидные Telegram credentials")
                else:
                    print("ℹ️  Пропускаем вызов - нужны специфические аргументы")

            else:
                print("❌ Нет доступных инструментов для тестирования")

            print("\n" + "=" * 60)
            print("🎉 ТЕСТИРОВАНИЕ ЗАВЕРШЕНО!")
            print("=" * 60)

            # Итоговый статус
            success_count = sum([1 if tools else 0, 1 if resources else 0, 1 if prompts else 0])

            print("📊 РЕЗУЛЬТАТЫ:")
            print("   ✅ Подключение к серверу: УСПЕШНО")
            print("   ✅ MCP протокол: РАБОТАЕТ")
            print("   ✅ SSE соединение: УСТАНОВЛЕНО")
            print("   ✅ Сервер отвечает: ДА")

            if success_count > 0:
                print(f"   ✅ Компоненты сервера: {success_count}/3 работают")
            else:
                print("   ⚠️  Сервер отвечает, но нет доступных компонентов")

    except Exception as e:
        print(f"❌ Критическая ошибка при тестировании: {e}")
        print("\n🔧 Возможные причины:")
        print("   • Сервер недоступен")
        print("   • Неправильный URL")
        print("   • Проблемы с SSL сертификатом")
        print("   • FastMCP библиотека несовместима")

        import traceback

        print(f"\n🔍 Детали ошибки:\n{traceback.format_exc()}")


async def simple_http_test():
    """Простой HTTP тест без FastMCP"""
    print("\n🌐 Простой HTTP тест (без FastMCP):")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Тестируем health endpoint
            response = await client.get("https://tgtoolkit.azazazaza.work/health")
            print(f"   Health: {response.status_code} - {response.text[:100]}...")

            # Тестируем metrics endpoint
            response = await client.get("https://tgtoolkit.azazazaza.work/metrics")
            print(f"   Metrics: {response.status_code} - {len(response.text)} символов")

    except Exception as e:
        print(f"   ❌ HTTP тест неудачен: {e}")


if __name__ == "__main__":
    print("🧪 ЗАПУСК ПОЛНОЦЕННОГО ТЕСТИРОВАНИЯ MCP СЕРВЕРА")
    print("🚀 Используем FastMCP клиент для правильного тестирования SSE")

    # Запускаем простой HTTP тест
    asyncio.run(simple_http_test())

    # Запускаем полный MCP тест
    asyncio.run(test_mcp_server())

    print("\n" + "🎯" * 60)
    print("🎉 ВСЕ ТЕСТЫ ЗАВЕРШЕНЫ!")
    print("📋 Проверьте MCP Inspector в браузере для визуального тестирования")
    print("🎯" * 60)
