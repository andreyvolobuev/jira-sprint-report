"""
Исследование API - поиск актуальных спринтов
"""

import requests
import json

BASE_URL = "https://jira.2gis.ru"
TOKEN = "MTA5MDAxNTc2MjgxOjD+AK/wJOqT7qwpycMM8mpGKYT1"

HEADERS = {
    "Accept": "application/json",
    "Authorization": f"Bearer {TOKEN}"
}


def get(url: str, params: dict = None):
    """GET запрос к API"""
    response = requests.get(url, headers=HEADERS, params=params, timeout=60)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Ошибка {response.status_code} для {url}: {response.text[:200]}")
        return None


def get_all_sprints(board_id: int) -> list:
    """Получить ВСЕ спринты доски с пагинацией"""
    all_sprints = []
    start_at = 0
    max_results = 50
    
    while True:
        data = get(
            f"{BASE_URL}/rest/agile/1.0/board/{board_id}/sprint",
            {"startAt": start_at, "maxResults": max_results}
        )
        if not data:
            break
        
        sprints = data.get('values', [])
        all_sprints.extend(sprints)
        
        if len(sprints) < max_results:
            break
        start_at += max_results
    
    return all_sprints


def main():
    # Добыча данных доска
    board_id = 803
    
    print("=" * 60)
    print(f"ВСЕ СПРИНТЫ ДОСКИ 'Добыча данных' (ID: {board_id})")
    print("=" * 60)
    
    sprints = get_all_sprints(board_id)
    print(f"\nВсего спринтов: {len(sprints)}")
    
    # Группируем по состоянию
    active = [s for s in sprints if s.get('state') == 'active']
    future = [s for s in sprints if s.get('state') == 'future']
    closed = [s for s in sprints if s.get('state') == 'closed']
    
    print(f"  Active: {len(active)}")
    print(f"  Future: {len(future)}")
    print(f"  Closed: {len(closed)}")
    
    # Показать активные
    if active:
        print(f"\n--- АКТИВНЫЕ СПРИНТЫ ---")
        for s in active:
            print(f"  ID: {s.get('id')}, Name: {s.get('name')}")
            print(f"    Start: {s.get('startDate')}")
            print(f"    End: {s.get('endDate')}")
    
    # Показать будущие
    if future:
        print(f"\n--- БУДУЩИЕ СПРИНТЫ ---")
        for s in future[:5]:
            print(f"  ID: {s.get('id')}, Name: {s.get('name')}")
    
    # Показать последние закрытые (отсортированные по ID)
    print(f"\n--- ПОСЛЕДНИЕ ЗАКРЫТЫЕ СПРИНТЫ ---")
    closed_sorted = sorted(closed, key=lambda x: x.get('id'), reverse=True)
    for s in closed_sorted[:10]:
        start = s.get('startDate', '')[:10] if s.get('startDate') else 'N/A'
        end = s.get('endDate', '')[:10] if s.get('endDate') else 'N/A'
        print(f"  ID: {s.get('id')}, {s.get('name')} ({start} - {end})")
    
    # Определяем целевой спринт (предыдущий перед активным)
    if active:
        active_id = active[0].get('id')
        print(f"\n--- ЦЕЛЕВОЙ СПРИНТ (предыдущий перед активным ID={active_id}) ---")
        
        # Ищем закрытый спринт с максимальным ID меньше активного
        candidates = [s for s in closed if s.get('id') < active_id]
        if candidates:
            target = max(candidates, key=lambda x: x.get('id'))
            print(json.dumps(target, indent=2, ensure_ascii=False, default=str))
            
            # Получим задачи этого спринта
            sprint_id = target.get('id')
            print(f"\n--- ПРИМЕР ЗАДАЧ ЦЕЛЕВОГО СПРИНТА (ID: {sprint_id}) ---")
            
            issues = get(
                f"{BASE_URL}/rest/agile/1.0/sprint/{sprint_id}/issue",
                {
                    "maxResults": 10,
                    "fields": "key,summary,status,assignee,customfield_10080,created",
                    "expand": "changelog"
                }
            )
            
            if issues:
                print(f"Всего задач в спринте: {issues.get('total', 0)}")
                for issue in issues.get('issues', [])[:3]:
                    key = issue.get('key')
                    fields = issue.get('fields', {})
                    sp = fields.get('customfield_10080', 0) or 0
                    assignee = fields.get('assignee', {})
                    assignee_name = assignee.get('displayName', 'Unassigned') if assignee else 'Unassigned'
                    status = fields.get('status', {}).get('name', 'N/A')
                    
                    print(f"\n  {key}: SP={sp}, Status={status}")
                    print(f"    Assignee: {assignee_name}")
                    
                    # Changelog - когда добавлено в спринт
                    changelog = issue.get('changelog', {})
                    for h in changelog.get('histories', []):
                        for item in h.get('items', []):
                            if item.get('field') == 'Sprint':
                                to_str = item.get('toString', '')
                                if target.get('name') in to_str:
                                    print(f"    Добавлено в спринт: {h.get('created')[:19]}")


if __name__ == "__main__":
    main()
