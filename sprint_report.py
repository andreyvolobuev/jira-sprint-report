"""
Отчет по спринтам для проектов DM и BOTS
"""

import requests
from datetime import datetime
from collections import defaultdict
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
    original: list = field(default_factory=list)  # Были на старте спринта (планировались)
    added_later: list = field(default_factory=list)  # Добавлены после старта (не планировались)
    carried_over: list = field(default_factory=list)  # Переехали из настоящих предыдущих спринтов
    closed_planned: list = field(default_factory=list)  # Закрыты из original (планировались и закрыты)
    closed_unplanned: list = field(default_factory=list)  # Закрыты из added_later (не планировались, но закрыты)


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
    # Формат: 2026-01-12T04:00:00.000+07:00
    try:
        # Убираем миллисекунды и таймзону для простоты
        clean = date_str[:19]
        return datetime.strptime(clean, "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None


# =============================================================================
# 1. Получение спринтов
# =============================================================================

def get_all_sprints(board_id: int) -> list[Sprint]:
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


def get_target_sprint(board_id: int) -> tuple[Sprint | None, Sprint | None, set[str]]:
    """
    Найти целевой спринт (предыдущий перед активным).
    Возвращает (target_sprint, active_sprint, real_sprint_names)
    """
    sprints = get_all_sprints(board_id)
    
    # Найти активный спринт
    active_sprints = [s for s in sprints if s.state == 'active']
    if not active_sprints:
        print("Не найден активный спринт!")
        return None, None, set()
    
    active = active_sprints[0]
    
    # Найти предыдущий закрытый спринт (максимальный ID меньше активного)
    closed_sprints = [s for s in sprints if s.state == 'closed' and s.id < active.id]
    if not closed_sprints:
        print("Не найден предыдущий закрытый спринт!")
        return None, active, set()
    
    target = max(closed_sprints, key=lambda x: x.id)
    
    # Собрать имена всех "настоящих" спринтов (для проверки carried_over)
    real_sprint_names = {s.name for s in sprints if is_real_sprint(s)}
    
    return target, active, real_sprint_names


# =============================================================================
# 2. Получение задач спринта
# =============================================================================

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
            
            # Собираем changelog
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


# =============================================================================
# 3. Анализ changelog
# =============================================================================

def parse_sprint_add_date(issue: Issue, sprint_name: str) -> datetime | None:
    """
    Определить дату добавления задачи в спринт из changelog.
    Возвращает самую раннюю дату добавления в указанный спринт.
    """
    add_dates = []
    
    for entry in issue.changelog:
        if entry['field'] == 'Sprint':
            to_value = entry['to'] or ''
            # Проверяем, что спринт появился в поле "to"
            if sprint_name in to_value:
                add_dates.append(entry['date'])
    
    if add_dates:
        return min(add_dates)
    
    # Если в changelog нет записи о добавлении в спринт,
    # значит задача была создана сразу в этом спринте
    return issue.created


def parse_status_closed_date(issue: Issue) -> datetime | None:
    """
    Определить дату перехода в статус Closed из changelog.
    Возвращает последнюю дату перехода в Closed.
    """
    closed_dates = []
    
    for entry in issue.changelog:
        if entry['field'] == 'status':
            to_value = entry['to'] or ''
            if to_value.lower() == 'closed':
                closed_dates.append(entry['date'])
    
    if closed_dates:
        return max(closed_dates)
    return None


def get_previous_real_sprints(issue: Issue, target_sprint_name: str, real_sprint_names: set[str]) -> list[str]:
    """
    Получить список НАСТОЯЩИХ предыдущих спринтов задачи (до целевого).
    Анализирует changelog, чтобы найти спринты, в которых задача была раньше.
    Возвращает только настоящие спринты (не технические очереди).
    """
    previous_sprints = set()
    
    for entry in issue.changelog:
        if entry['field'] == 'Sprint':
            from_value = entry['from'] or ''
            to_value = entry['to'] or ''
            
            # Если задача переехала в целевой спринт из другого
            if target_sprint_name in to_value and from_value:
                # from_value может содержать несколько спринтов через запятую
                for sprint in from_value.split(','):
                    sprint = sprint.strip()
                    # Проверяем что это настоящий спринт, а не технический
                    if sprint and sprint != target_sprint_name and sprint in real_sprint_names:
                        previous_sprints.add(sprint)
    
    return list(previous_sprints)


# =============================================================================
# 4. Категоризация задач
# =============================================================================

def categorize_issues(
    issues: list[Issue],
    sprint_name: str,
    sprint_start: datetime,
    sprint_end: datetime,
    real_sprint_names: set[str]
) -> dict[str, DeveloperStats]:
    """
    Разделить задачи на категории по разработчикам.
    
    Категории:
    - original: задачи в спринте на момент старта (планировались)
    - added_later: задачи добавленные после старта (не планировались)
    - carried_over: задачи переехавшие из НАСТОЯЩИХ предыдущих спринтов
    - closed_planned: из original, закрыты в спринте
    - closed_unplanned: из added_later, закрыты в спринте
    """
    stats_by_developer = defaultdict(lambda: DeveloperStats(name=""))
    
    for issue in issues:
        dev_key = issue.assignee_key
        if stats_by_developer[dev_key].name == "":
            stats_by_developer[dev_key].name = issue.assignee
        
        stats = stats_by_developer[dev_key]
        
        # Определяем когда задача была добавлена в спринт
        add_date = parse_sprint_add_date(issue, sprint_name)
        
        # Определяем была ли задача в НАСТОЯЩИХ предыдущих спринтах
        prev_sprints = get_previous_real_sprints(issue, sprint_name, real_sprint_names)
        
        # Определяем дату закрытия
        closed_date = parse_status_closed_date(issue)
        is_closed_in_sprint = (
            closed_date is not None and 
            closed_date <= sprint_end
        )
        
        # Категоризация
        is_original = add_date is not None and add_date <= sprint_start
        is_added_later = add_date is not None and add_date > sprint_start
        is_carried_over = len(prev_sprints) > 0
        
        # original: были на старте спринта (планировались)
        if is_original:
            stats.original.append(issue)
        
        # added_later: добавлены после старта (не планировались)
        if is_added_later:
            stats.added_later.append(issue)
        
        # carried_over: переехали из настоящих предыдущих спринтов
        if is_carried_over:
            stats.carried_over.append(issue)
        
        # closed_planned: закрыты из original (планировались и закрыты)
        if is_original and is_closed_in_sprint:
            stats.closed_planned.append(issue)
        
        # closed_unplanned: закрыты из added_later (не планировались, но закрыты)
        if is_added_later and is_closed_in_sprint:
            stats.closed_unplanned.append(issue)
    
    return dict(stats_by_developer)


# =============================================================================
# 5. Формирование отчета
# =============================================================================

def sum_story_points(issues: list[Issue]) -> float:
    """Сумма story points"""
    return sum(i.story_points for i in issues)


def print_issues_table(issues: list[Issue], title: str):
    """Вывести таблицу задач"""
    if not issues:
        print(f"\n  {title}: нет задач")
        return
    
    total_sp = sum_story_points(issues)
    print(f"\n  {title} ({len(issues)} задач, {total_sp} SP):")
    print(f"  {'─'*70}")
    print(f"  {'Задача':<12} {'SP':>5}  {'Название':<50}")
    print(f"  {'─'*70}")
    
    for issue in sorted(issues, key=lambda x: x.key):
        summary = issue.summary[:47] + "..." if len(issue.summary) > 50 else issue.summary
        print(f"  {issue.key:<12} {issue.story_points:>5.1f}  {summary:<50}")
    
    print(f"  {'─'*70}")
    print(f"  {'ИТОГО':<12} {total_sp:>5.1f}")


def print_report(
    stats_by_developer: dict[str, DeveloperStats],
    target_sprint: Sprint
):
    """Вывести полный отчет"""
    print("=" * 80)
    print(f"ОТЧЕТ ПО СПРИНТУ: {target_sprint.name}")
    print(f"Период: {target_sprint.start_date.strftime('%Y-%m-%d')} - {target_sprint.end_date.strftime('%Y-%m-%d')}")
    print("=" * 80)
    
    # Агрегаты по команде
    team_original_sp = 0
    team_added_later_sp = 0
    team_carried_over_sp = 0
    team_closed_planned_sp = 0
    team_closed_unplanned_sp = 0
    
    # По каждому разработчику
    for dev_key, stats in sorted(stats_by_developer.items(), key=lambda x: x[1].name):
        if stats.name == "Unassigned":
            continue
            
        print(f"\n{'━'*80}")
        print(f"РАЗРАБОТЧИК: {stats.name}")
        print(f"{'━'*80}")
        
        # 1. Original - были на старте (планировались)
        print_issues_table(stats.original, "Планировались (original)")
        team_original_sp += sum_story_points(stats.original)
        
        # 2. Added later - добавлены после старта (не планировались)
        print_issues_table(stats.added_later, "Не планировались (added_later)")
        team_added_later_sp += sum_story_points(stats.added_later)
        
        # 3. Carried over - переехали из предыдущих спринтов
        print_issues_table(stats.carried_over, "Переехали из предыдущих спринтов (carried_over)")
        team_carried_over_sp += sum_story_points(stats.carried_over)
        
        # 4. Closed planned - закрыты из original
        print_issues_table(stats.closed_planned, "Планировались и закрыты (closed_planned)")
        team_closed_planned_sp += sum_story_points(stats.closed_planned)
        
        # 5. Closed unplanned - закрыты из added_later
        print_issues_table(stats.closed_unplanned, "Не планировались, но закрыты (closed_unplanned)")
        team_closed_unplanned_sp += sum_story_points(stats.closed_unplanned)
    
    # Unassigned отдельно
    if 'unassigned' in stats_by_developer:
        stats = stats_by_developer['unassigned']
        print(f"\n{'━'*80}")
        print(f"БЕЗ ИСПОЛНИТЕЛЯ (Unassigned)")
        print(f"{'━'*80}")
        print_issues_table(stats.original, "Планировались")
        print_issues_table(stats.added_later, "Не планировались")
        
        team_original_sp += sum_story_points(stats.original)
        team_added_later_sp += sum_story_points(stats.added_later)
        team_carried_over_sp += sum_story_points(stats.carried_over)
        team_closed_planned_sp += sum_story_points(stats.closed_planned)
        team_closed_unplanned_sp += sum_story_points(stats.closed_unplanned)
    
    # Итоги по команде
    print(f"\n{'='*80}")
    print("ИТОГИ ПО КОМАНДЕ")
    print(f"{'='*80}")
    print(f"  {'Категория':<50} {'SP':>10}")
    print(f"  {'-'*60}")
    print(f"  {'Планировались (original)':<50} {team_original_sp:>10.1f}")
    print(f"  {'Не планировались (added_later)':<50} {team_added_later_sp:>10.1f}")
    print(f"  {'Переехали из предыдущих спринтов (carried_over)':<50} {team_carried_over_sp:>10.1f}")
    print(f"  {'Планировались и закрыты (closed_planned)':<50} {team_closed_planned_sp:>10.1f}")
    print(f"  {'Не планировались, но закрыты (closed_unplanned)':<50} {team_closed_unplanned_sp:>10.1f}")
    print(f"  {'-'*60}")


# =============================================================================
# 6. Main
# =============================================================================

def build_report(board_id: int = BOARD_ID):
    """Собрать и вывести отчет"""
    print("Получение спринтов...")
    target_sprint, active_sprint, real_sprint_names = get_target_sprint(board_id)
    
    if not target_sprint:
        print("Не удалось определить целевой спринт!")
        return
    
    print(f"Активный спринт: {active_sprint.name} (ID: {active_sprint.id})")
    print(f"Целевой спринт: {target_sprint.name} (ID: {target_sprint.id})")
    print(f"Период: {target_sprint.start_date} - {target_sprint.end_date}")
    print(f"Настоящих спринтов для анализа carried_over: {len(real_sprint_names)}")
    
    print("\nПолучение задач спринта...")
    issues = get_sprint_issues_with_changelog(target_sprint.id)
    print(f"Получено задач: {len(issues)}")
    
    print("\nКатегоризация задач...")
    stats = categorize_issues(
        issues,
        target_sprint.name,
        target_sprint.start_date,
        target_sprint.end_date,
        real_sprint_names
    )
    
    print(f"Разработчиков: {len(stats)}")
    
    print_report(stats, target_sprint)


def main():
    """Точка входа"""
    build_report()


if __name__ == "__main__":
    main()
