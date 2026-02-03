"""
Общие функции для работы с Jira API
"""

import requests
from datetime import datetime
from dataclasses import dataclass, field

# Конфигурация
BASE_URL = "https://jira.2gis.ru"
TOKEN = "MTA5MDAxNTc2MjgxOjD+AK/wJOqT7qwpycMM8mpGKYT1"
BOARD_ID = 803  # Добыча данных
STORY_POINTS_FIELD = "customfield_10080"

HEADERS = {
    "Accept": "application/json",
    "Authorization": f"Bearer {TOKEN}"
}


@dataclass
class Issue:
    """Задача Jira"""
    key: str
    summary: str
    story_points: float
    status: str
    assignee: str
    assignee_key: str
    created: datetime
    changelog: list = field(default_factory=list)


@dataclass
class Sprint:
    """Спринт"""
    id: int
    name: str
    state: str
    start_date: datetime | None
    end_date: datetime | None
    activated_date: datetime | None
    complete_date: datetime | None


@dataclass
class DeveloperStats:
    """Статистика разработчика"""
    name: str
    original: list = field(default_factory=list)
    added_later: list = field(default_factory=list)
    carried_over: list = field(default_factory=list)
    closed_planned: list = field(default_factory=list)
    closed_unplanned: list = field(default_factory=list)


def get(url: str, params: dict = None) -> dict | list | None:
    """GET запрос к API"""
    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=120)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Ошибка {response.status_code}: {response.text[:200]}")
            return None
    except Exception as e:
        print(f"Исключение при запросе {url}: {e}")
        return None


def parse_datetime(date_str: str | None) -> datetime | None:
    """Парсинг даты из Jira формата"""
    if not date_str:
        return None
    try:
        clean = date_str[:19]
        return datetime.strptime(clean, "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None


def is_real_sprint(sprint: Sprint) -> bool:
    """
    Проверить, является ли спринт "настоящим" (не техническим).
    Настоящий спринт: закрыт, имеет даты начала и окончания, дата окончания прошла.
    """
    if sprint.state != 'closed':
        return False
    if sprint.start_date is None or sprint.end_date is None:
        return False
    if sprint.end_date > datetime.now():
        return False
    return True


def get_all_sprints(board_id: int = BOARD_ID) -> list[Sprint]:
    """Получить все спринты доски с пагинацией"""
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
        
        for s in data.get('values', []):
            sprint = Sprint(
                id=s.get('id'),
                name=s.get('name'),
                state=s.get('state'),
                start_date=parse_datetime(s.get('startDate')),
                end_date=parse_datetime(s.get('endDate')),
                activated_date=parse_datetime(s.get('activatedDate')),
                complete_date=parse_datetime(s.get('completeDate'))
            )
            all_sprints.append(sprint)
        
        if len(data.get('values', [])) < max_results:
            break
        start_at += max_results
    
    return all_sprints


def get_sprint_by_id(sprint_id: int, board_id: int = BOARD_ID) -> Sprint | None:
    """Получить спринт по ID"""
    data = get(f"{BASE_URL}/rest/agile/1.0/sprint/{sprint_id}")
    if not data:
        return None
    
    return Sprint(
        id=data.get('id'),
        name=data.get('name'),
        state=data.get('state'),
        start_date=parse_datetime(data.get('startDate')),
        end_date=parse_datetime(data.get('endDate')),
        activated_date=parse_datetime(data.get('activatedDate')),
        complete_date=parse_datetime(data.get('completeDate'))
    )


def get_real_sprint_names(board_id: int = BOARD_ID) -> set[str]:
    """Получить имена всех настоящих спринтов"""
    sprints = get_all_sprints(board_id)
    return {s.name for s in sprints if is_real_sprint(s)}


def get_sprint_issues_with_changelog(sprint_id: int) -> list[Issue]:
    """Получить все задачи спринта с полным changelog"""
    all_issues = []
    start_at = 0
    max_results = 50
    
    while True:
        data = get(
            f"{BASE_URL}/rest/agile/1.0/sprint/{sprint_id}/issue",
            {
                "startAt": start_at,
                "maxResults": max_results,
                "fields": f"key,summary,status,assignee,{STORY_POINTS_FIELD},created",
                "expand": "changelog"
            }
        )
        if not data:
            break
        
        for i in data.get('issues', []):
            fields = i.get('fields', {})
            assignee = fields.get('assignee') or {}
            
            changelog_data = i.get('changelog', {})
            histories = []
            for h in changelog_data.get('histories', []):
                history_date = parse_datetime(h.get('created'))
                for item in h.get('items', []):
                    histories.append({
                        'date': history_date,
                        'field': item.get('field'),
                        'from': item.get('fromString'),
                        'to': item.get('toString')
                    })
            
            issue = Issue(
                key=i.get('key'),
                summary=fields.get('summary', ''),
                story_points=fields.get(STORY_POINTS_FIELD) or 0,
                status=fields.get('status', {}).get('name', 'Unknown'),
                assignee=assignee.get('displayName', 'Unassigned'),
                assignee_key=assignee.get('key', 'unassigned'),
                created=parse_datetime(fields.get('created')),
                changelog=histories
            )
            all_issues.append(issue)
        
        total = data.get('total', 0)
        if start_at + max_results >= total:
            break
        start_at += max_results
    
    return all_issues
