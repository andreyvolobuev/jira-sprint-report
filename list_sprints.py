"""
Вывод списка спринтов доски
"""

from jira_client import get_all_sprints, BOARD_ID


def main():
    print("Получение списка спринтов...")
    sprints = get_all_sprints(BOARD_ID)
    
    # Группируем по состоянию
    active = [s for s in sprints if s.state == 'active']
    closed = [s for s in sprints if s.state == 'closed']
    future = [s for s in sprints if s.state == 'future']
    
    # Сортируем закрытые по ID (новые сверху)
    closed_sorted = sorted(closed, key=lambda x: x.id, reverse=True)
    
    print(f"\nВсего спринтов: {len(sprints)}")
    print(f"  Active: {len(active)}, Closed: {len(closed)}, Future: {len(future)}")
    
    # Активные
    if active:
        print(f"\n{'='*70}")
        print("АКТИВНЫЕ СПРИНТЫ")
        print(f"{'='*70}")
        print(f"{'ID':<8} {'Название':<40} {'Период'}")
        print(f"{'-'*70}")
        for s in active:
            start = s.start_date.strftime('%Y-%m-%d') if s.start_date else 'N/A'
            end = s.end_date.strftime('%Y-%m-%d') if s.end_date else 'N/A'
            print(f"{s.id:<8} {s.name:<40} {start} - {end}")
    
    # Закрытые (последние 20)
    print(f"\n{'='*70}")
    print("ЗАКРЫТЫЕ СПРИНТЫ (последние 20)")
    print(f"{'='*70}")
    print(f"{'ID':<8} {'Название':<40} {'Период'}")
    print(f"{'-'*70}")
    for s in closed_sorted[:20]:
        start = s.start_date.strftime('%Y-%m-%d') if s.start_date else 'N/A'
        end = s.end_date.strftime('%Y-%m-%d') if s.end_date else 'N/A'
        print(f"{s.id:<8} {s.name:<40} {start} - {end}")
    
    # Будущие
    if future:
        print(f"\n{'='*70}")
        print("БУДУЩИЕ СПРИНТЫ")
        print(f"{'='*70}")
        print(f"{'ID':<8} {'Название':<40}")
        print(f"{'-'*70}")
        for s in future[:10]:
            print(f"{s.id:<8} {s.name:<40}")
    
    print(f"\n{'='*70}")
    print("Для генерации отчета используйте:")
    print("  python sprint_report.py <sprint_id>")
    print("  python sprint_report.py          # без аргумента = предыдущий спринт")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
