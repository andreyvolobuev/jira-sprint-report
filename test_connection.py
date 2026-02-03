"""
Тестовый скрипт для проверки подключения к Jira API
"""

import requests
import json

# Конфигурация
BASE_URL = "https://jira.2gis.ru"
TOKEN = "MTA5MDAxNTc2MjgxOjD+AK/wJOqT7qwpycMM8mpGKYT1"

HEADERS = {
    "Accept": "application/json",
    "Authorization": f"Bearer {TOKEN}"
}


def test_endpoint(name: str, url: str, params: dict = None) -> dict | list | None:
    """Проверка доступности endpoint'а"""
    print(f"\n{'='*60}")
    print(f"Проверка: {name}")
    print(f"URL: {url}")
    print("-" * 60)
    
    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=30)
        print(f"Статус: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Успешно! Тип данных: {type(data).__name__}")
            return data
        else:
            print(f"Ошибка: {response.text[:300]}")
            return None
    except Exception as e:
        print(f"Исключение: {e}")
        return None


def main():
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ JIRA API")
    print("=" * 60)
    
    # 1. Информация о сервере
    server_info = test_endpoint(
        "Информация о сервере",
        f"{BASE_URL}/rest/api/2/serverInfo"
    )
    if server_info:
        print(f"  Версия Jira: {server_info.get('version', 'N/A')}")
        print(f"  Build: {server_info.get('buildNumber', 'N/A')}")
        print(f"  Deployment: {server_info.get('deploymentType', 'N/A')}")
        print(f"  Base URL: {server_info.get('baseUrl', 'N/A')}")
    
    # 2. Текущий пользователь
    myself = test_endpoint(
        "Текущий пользователь",
        f"{BASE_URL}/rest/api/2/myself"
    )
    if myself:
        print(f"  Имя: {myself.get('displayName', 'N/A')}")
        print(f"  Email: {myself.get('emailAddress', 'N/A')}")
        print(f"  Username: {myself.get('name', 'N/A')}")
        print(f"  Active: {myself.get('active', 'N/A')}")
        print(f"  Timezone: {myself.get('timeZone', 'N/A')}")
    
    # 3. Проверка API v3
    api3 = test_endpoint(
        "API v3 - serverInfo (проверка доступности)",
        f"{BASE_URL}/rest/api/3/serverInfo"
    )
    if api3:
        print("  API v3 доступен!")
    else:
        print("  API v3 недоступен, используем v2")
    
    # 4. Список проектов
    projects = test_endpoint(
        "Список проектов",
        f"{BASE_URL}/rest/api/2/project"
    )
    if projects:
        print(f"  Всего проектов: {len(projects)}")
        print("  Первые 10 проектов:")
        for p in projects[:10]:
            print(f"    - {p.get('key')}: {p.get('name')}")
    
    # 5. Доступные поля
    fields = test_endpoint(
        "Список полей",
        f"{BASE_URL}/rest/api/2/field"
    )
    if fields:
        standard_fields = [f for f in fields if not f.get('custom')]
        custom_fields = [f for f in fields if f.get('custom')]
        print(f"  Стандартных полей: {len(standard_fields)}")
        print(f"  Кастомных полей: {len(custom_fields)}")
        print("  Примеры кастомных полей:")
        for f in custom_fields[:5]:
            print(f"    - {f.get('id')}: {f.get('name')}")
    
    # 6. Типы задач
    issue_types = test_endpoint(
        "Типы задач",
        f"{BASE_URL}/rest/api/2/issuetype"
    )
    if issue_types:
        print(f"  Всего типов: {len(issue_types)}")
        for it in issue_types[:10]:
            subtask = " (subtask)" if it.get('subtask') else ""
            print(f"    - {it.get('name')}{subtask}")
    
    # 7. Статусы
    statuses = test_endpoint(
        "Статусы задач",
        f"{BASE_URL}/rest/api/2/status"
    )
    if statuses:
        print(f"  Всего статусов: {len(statuses)}")
        for s in statuses[:10]:
            category = s.get('statusCategory', {}).get('name', 'N/A')
            print(f"    - {s.get('name')} [{category}]")
    
    # 8. Приоритеты
    priorities = test_endpoint(
        "Приоритеты",
        f"{BASE_URL}/rest/api/2/priority"
    )
    if priorities:
        print(f"  Приоритеты:")
        for p in priorities:
            print(f"    - {p.get('name')}")
    
    # 9. JQL поиск
    print(f"\n{'='*60}")
    print("Проверка: JQL поиск (последние 5 задач)")
    print("-" * 60)
    
    try:
        response = requests.get(
            f"{BASE_URL}/rest/api/2/search",
            headers=HEADERS,
            params={
                "jql": "order by created DESC",
                "maxResults": 5,
                "fields": "key,summary,status,assignee,created,project"
            },
            timeout=30
        )
        print(f"Статус: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"  Всего задач в системе: {data.get('total', 0)}")
            print("  Последние задачи:")
            for issue in data.get('issues', []):
                key = issue.get('key')
                f = issue.get('fields', {})
                summary = f.get('summary', 'N/A')[:40]
                status = f.get('status', {}).get('name', 'N/A')
                project = f.get('project', {}).get('name', 'N/A')
                print(f"    - {key}: {summary}... [{status}] ({project})")
        else:
            print(f"Ошибка: {response.text[:300]}")
    except Exception as e:
        print(f"Исключение: {e}")
    
    # 10. Мои задачи (assigned to me)
    print(f"\n{'='*60}")
    print("Проверка: Мои задачи")
    print("-" * 60)
    
    try:
        response = requests.get(
            f"{BASE_URL}/rest/api/2/search",
            headers=HEADERS,
            params={
                "jql": "assignee = currentUser() ORDER BY updated DESC",
                "maxResults": 5,
                "fields": "key,summary,status"
            },
            timeout=30
        )
        print(f"Статус: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"  Всего моих задач: {data.get('total', 0)}")
            print("  Последние мои задачи:")
            for issue in data.get('issues', []):
                key = issue.get('key')
                f = issue.get('fields', {})
                summary = f.get('summary', 'N/A')[:40]
                status = f.get('status', {}).get('name', 'N/A')
                print(f"    - {key}: {summary}... [{status}]")
        else:
            print(f"Ошибка: {response.text[:300]}")
    except Exception as e:
        print(f"Исключение: {e}")
    
    # 11. Фильтры (избранные)
    filters = test_endpoint(
        "Мои фильтры",
        f"{BASE_URL}/rest/api/2/filter/favourite"
    )
    if filters:
        print(f"  Избранных фильтров: {len(filters)}")
        for f in filters[:5]:
            print(f"    - {f.get('name')}: {f.get('jql', 'N/A')[:50]}...")
    
    # 12. Доски (если есть Agile/Jira Software)
    boards = test_endpoint(
        "Agile доски",
        f"{BASE_URL}/rest/agile/1.0/board"
    )
    if boards and isinstance(boards, dict):
        values = boards.get('values', [])
        print(f"  Всего досок: {boards.get('total', len(values))}")
        for b in values[:5]:
            print(f"    - {b.get('name')} ({b.get('type')})")
    
    # 13. Спринты (если есть доски)
    if boards and isinstance(boards, dict) and boards.get('values'):
        first_board = boards['values'][0]
        board_id = first_board.get('id')
        sprints = test_endpoint(
            f"Спринты для доски '{first_board.get('name')}'",
            f"{BASE_URL}/rest/agile/1.0/board/{board_id}/sprint"
        )
        if sprints and isinstance(sprints, dict):
            values = sprints.get('values', [])
            print(f"  Всего спринтов: {len(values)}")
            for s in values[:5]:
                state = s.get('state', 'N/A')
                print(f"    - {s.get('name')} [{state}]")
    
    print(f"\n{'='*60}")
    print("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print("=" * 60)
    print("\nИТОГО:")
    print("- Аутентификация: Bearer Token")
    print(f"- API версия: {'v3' if api3 else 'v2'}")
    print(f"- Проектов доступно: {len(projects) if projects else 0}")


if __name__ == "__main__":
    main()
