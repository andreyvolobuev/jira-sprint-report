"""
Отчет по спринту

Использование:
    python sprint_report.py -id <sprint_id>
    
Пример:
    python sprint_report.py -id 6783
"""

import argparse
from datetime import datetime
from collections import defaultdict

from jira_client import (
    Issue, Sprint, DeveloperStats,
    get_sprint_by_id, get_real_sprint_names,
    get_sprint_issues_with_changelog
)


# =============================================================================
# Анализ changelog
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
            if sprint_name in to_value:
                add_dates.append(entry['date'])
    
    if add_dates:
        return min(add_dates)
    
    return issue.created


def parse_status_closed_date(issue: Issue) -> datetime | None:
    """
    Определить дату перехода в статус Closed из changelog.
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
    Получить список НАСТОЯЩИХ предыдущих спринтов задачи.
    """
    previous_sprints = set()
    
    for entry in issue.changelog:
        if entry['field'] == 'Sprint':
            from_value = entry['from'] or ''
            to_value = entry['to'] or ''
            
            if target_sprint_name in to_value and from_value:
                for sprint in from_value.split(','):
                    sprint = sprint.strip()
                    if sprint and sprint != target_sprint_name and sprint in real_sprint_names:
                        previous_sprints.add(sprint)
    
    return list(previous_sprints)


# =============================================================================
# Категоризация задач
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
        
        add_date = parse_sprint_add_date(issue, sprint_name)
        prev_sprints = get_previous_real_sprints(issue, sprint_name, real_sprint_names)
        closed_date = parse_status_closed_date(issue)
        
        is_closed_in_sprint = (
            closed_date is not None and 
            closed_date <= sprint_end
        )
        
        is_original = add_date is not None and add_date <= sprint_start
        is_added_later = add_date is not None and add_date > sprint_start
        is_carried_over = len(prev_sprints) > 0
        
        if is_original:
            stats.original.append(issue)
        
        if is_added_later:
            stats.added_later.append(issue)
        
        if is_carried_over:
            stats.carried_over.append(issue)
        
        if is_original and is_closed_in_sprint:
            stats.closed_planned.append(issue)
        
        if is_added_later and is_closed_in_sprint:
            stats.closed_unplanned.append(issue)
    
    return dict(stats_by_developer)


# =============================================================================
# Формирование отчета
# =============================================================================

def sum_story_points(issues: list[Issue]) -> float:
    return sum(i.story_points for i in issues)


def print_issues_table(issues: list[Issue], title: str):
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


def print_report(stats_by_developer: dict[str, DeveloperStats], target_sprint: Sprint):
    print("=" * 80)
    print(f"ОТЧЕТ ПО СПРИНТУ: {target_sprint.name}")
    print(f"Период: {target_sprint.start_date.strftime('%Y-%m-%d')} - {target_sprint.end_date.strftime('%Y-%m-%d')}")
    print("=" * 80)
    
    team_original_sp = 0
    team_added_later_sp = 0
    team_carried_over_sp = 0
    team_closed_planned_sp = 0
    team_closed_unplanned_sp = 0
    
    for dev_key, stats in sorted(stats_by_developer.items(), key=lambda x: x[1].name):
        if stats.name == "Unassigned":
            continue
            
        print(f"\n{'━'*80}")
        print(f"РАЗРАБОТЧИК: {stats.name}")
        print(f"{'━'*80}")
        
        print_issues_table(stats.original, "Планировались (original)")
        team_original_sp += sum_story_points(stats.original)
        
        print_issues_table(stats.added_later, "Не планировались (added_later)")
        team_added_later_sp += sum_story_points(stats.added_later)
        
        print_issues_table(stats.carried_over, "Переехали из предыдущих спринтов (carried_over)")
        team_carried_over_sp += sum_story_points(stats.carried_over)
        
        print_issues_table(stats.closed_planned, "Планировались и закрыты (closed_planned)")
        team_closed_planned_sp += sum_story_points(stats.closed_planned)
        
        print_issues_table(stats.closed_unplanned, "Не планировались, но закрыты (closed_unplanned)")
        team_closed_unplanned_sp += sum_story_points(stats.closed_unplanned)
    
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
# Main
# =============================================================================

def build_report(sprint_id: int):
    """Собрать и вывести отчет"""
    print("Получение данных...")
    
    target_sprint = get_sprint_by_id(sprint_id)
    if not target_sprint:
        print(f"Спринт с ID {sprint_id} не найден!")
        return
    
    print(f"Целевой спринт: {target_sprint.name} (ID: {target_sprint.id})")
    print(f"Период: {target_sprint.start_date} - {target_sprint.end_date}")
    
    # Получаем имена настоящих спринтов для анализа carried_over
    real_sprint_names = get_real_sprint_names()
    print(f"Настоящих спринтов для анализа: {len(real_sprint_names)}")
    
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
    parser = argparse.ArgumentParser(
        description="Отчет по спринту",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Пример: python sprint_report.py -id 6783"
    )
    parser.add_argument(
        "-id",
        type=int,
        required=True,
        help="ID спринта (получить список: python list_sprints.py)"
    )
    
    args = parser.parse_args()
    build_report(args.id)


if __name__ == "__main__":
    main()
