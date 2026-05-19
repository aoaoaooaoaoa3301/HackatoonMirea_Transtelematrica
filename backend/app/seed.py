"""Idempotent seed script. Creates demo departments, users, and tasks.

Uses uuid5 with a fixed namespace so IDs are deterministic across runs.
"""
import logging
import uuid
from datetime import date, datetime, timedelta, timezone

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models.department import Department
from app.models.user import User
from app.models.task import Task, TaskHistory, TaskComment
from app.models.enums import UserRole, TaskType, TaskPriority, TaskStatus

logger = logging.getLogger(__name__)

NS = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")


def _id(name: str) -> uuid.UUID:
    return uuid.uuid5(NS, name)


DEFAULT_PASSWORD = hash_password("password")


def run_seed():
    db = SessionLocal()
    try:
        # Idempotent check
        admin = db.get(User, _id("admin"))
        if admin is not None:
            logger.info("Seed data already exists, skipping.")
            return
        logger.info("Seeding database...")

        # --- Departments ---
        depts = {
            "HR": _id("dept-HR"),
            "АХО": _id("dept-AHO"),
            "ИТ": _id("dept-IT"),
            "Финансы": _id("dept-FIN"),
            "Юридический отдел": _id("dept-LEGAL"),
            "Молодые таланты": _id("dept-TALENTS"),
            "Проектный офис": _id("dept-PMO"),
        }
        for name, did in depts.items():
            db.add(Department(id=did, name=name))
        db.flush()

        # --- Users ---
        users_data = [
            ("admin", "admin@ttm.local", "Анна Смирнова", UserRole.ADMIN, None, [], None),
            ("lead.talents", "lead.talents@ttm.local", "Иван Петров", UserRole.LEAD, "Молодые таланты", ["партнёрства", "вузы", "рекрутинг"], "senior"),
            ("lead.hr", "lead.hr@ttm.local", "Ольга Иванова", UserRole.LEAD, "HR", ["найм", "адаптация", "документы"], "senior"),
            ("lead.aho", "lead.aho@ttm.local", "Мария Соколова", UserRole.LEAD, "АХО", ["офис", "закупки"], "middle"),
            ("lead.it", "lead.it@ttm.local", "Сергей Кузнецов", UserRole.LEAD, "ИТ", ["devops", "инфраструктура"], "senior"),
            ("lead.fin", "lead.fin@ttm.local", "Татьяна Зайцева", UserRole.LEAD, "Финансы", ["отчётность", "бюджет"], "senior"),
            ("alex", "alex@ttm.local", "Алексей Новиков", UserRole.EMPLOYEE, "АХО", ["офис", "мероприятия"], "middle"),
            ("anna.hr", "anna.hr@ttm.local", "Анна Лебедева", UserRole.EMPLOYEE, "HR", ["найм", "отчёты"], "middle"),
            ("dmitry", "dmitry@ttm.local", "Дмитрий Орлов", UserRole.EMPLOYEE, "ИТ", ["доступы", "sysadmin"], "middle"),
            ("elena", "elena@ttm.local", "Елена Васильева", UserRole.EMPLOYEE, "Финансы", ["отчётность"], "middle"),
            ("pavel", "pavel@ttm.local", "Павел Соловьёв", UserRole.EMPLOYEE, "Молодые таланты", ["вузы", "мероприятия"], "junior"),
        ]

        user_ids = {}
        for key, email, name, role, dept_name, skills, seniority in users_data:
            uid = _id(key)
            user_ids[key] = uid
            dept_id = depts.get(dept_name) if dept_name else None
            db.add(User(
                id=uid,
                email=email,
                full_name=name,
                role=role,
                department_id=dept_id,
                password_hash=DEFAULT_PASSWORD,
                skills=skills,
                seniority=seniority,
            ))
        db.flush()

        # Set department heads
        head_map = {
            "HR": "lead.hr",
            "АХО": "lead.aho",
            "ИТ": "lead.it",
            "Финансы": "lead.fin",
            "Молодые таланты": "lead.talents",
        }
        for dept_name, user_key in head_map.items():
            dept = db.get(Department, depts[dept_name])
            dept.head_user_id = user_ids[user_key]
        db.flush()

        # --- Tasks ---
        admin_id = user_ids["admin"]

        # Helper to create task + history
        def mk_task(key, **kwargs):
            tid = _id(f"task-{key}")
            created_by = kwargs.pop("created_by", admin_id)
            t = Task(id=tid, created_by_id=created_by, **kwargs)
            db.add(t)
            db.add(TaskHistory(
                id=_id(f"hist-{key}"),
                task_id=tid,
                actor_id=created_by,
                event_type="created",
                payload={"title": kwargs.get("title", "")},
            ))
            return tid

        # 1. GOAL
        t1 = mk_task("1",
            type=TaskType.GOAL, title="Развить партнёрство с 5 вузами",
            assignee_id=user_ids["lead.talents"],
            assigned_department_id=depts["Молодые таланты"],
            start_date=date(2026, 1, 1), due_date=date(2026, 12, 31),
            priority=TaskPriority.HIGH, status=TaskStatus.IN_PROGRESS, progress=35,
            created_by=user_ids["admin"],
        )

        # 2. EPIC under #1
        t2 = mk_task("2",
            type=TaskType.EPIC, title="Заключить соглашение с МИРЭА",
            parent_id=t1,
            assignee_id=user_ids["lead.talents"],
            assigned_department_id=depts["Молодые таланты"],
            start_date=date(2026, 4, 1), due_date=date(2026, 6, 30),
            priority=TaskPriority.HIGH, status=TaskStatus.REVIEW, progress=70,
            created_by=user_ids["admin"],
        )

        # 3. TASK under #2
        t3 = mk_task("3",
            type=TaskType.TASK, title="Подготовить участие в хакатоне",
            parent_id=t2,
            assignee_id=user_ids["lead.talents"],
            assigned_department_id=depts["Молодые таланты"],
            start_date=date(2026, 5, 1), due_date=date(2026, 5, 31),
            priority=TaskPriority.HIGH, status=TaskStatus.IN_PROGRESS, progress=60,
            created_by=user_ids["lead.talents"],
        )

        # 4. SUBTASK under #3
        t4 = mk_task("4",
            type=TaskType.SUBTASK, title="Согласовать постановку кейса",
            parent_id=t3,
            assignee_id=user_ids["lead.talents"],
            assigned_department_id=depts["Молодые таланты"],
            due_date=date(2026, 5, 22),
            priority=TaskPriority.HIGH, status=TaskStatus.NEW, progress=0,
            created_by=user_ids["lead.talents"],
        )

        # 5. SUBTASK under #3
        t5 = mk_task("5",
            type=TaskType.SUBTASK, title="Подготовить призовой фонд",
            parent_id=t3,
            assignee_id=user_ids["pavel"],
            assigned_department_id=depts["Молодые таланты"],
            due_date=date(2026, 5, 25),
            priority=TaskPriority.MEDIUM, status=TaskStatus.IN_PROGRESS, progress=40,
            created_by=user_ids["lead.talents"],
        )

        # 6. TASK (standalone)
        t6 = mk_task("6",
            type=TaskType.TASK, title="Подготовить рабочие места для стажёров",
            assignee_id=user_ids["lead.aho"],
            assigned_department_id=depts["АХО"],
            start_date=date(2026, 5, 10), due_date=date(2026, 6, 10),
            priority=TaskPriority.MEDIUM, status=TaskStatus.NEW, progress=0,
            created_by=user_ids["admin"],
        )

        # 7. SUBTASK under #6
        t7 = mk_task("7",
            type=TaskType.SUBTASK, title="Проверить переговорные перед мероприятием",
            parent_id=t6,
            assignee_id=user_ids["alex"],
            assigned_department_id=depts["АХО"],
            due_date=date(2026, 5, 21),
            priority=TaskPriority.MEDIUM, status=TaskStatus.IN_PROGRESS, progress=50,
            created_by=user_ids["lead.aho"],
        )

        # 8. EPIC (standalone)
        t8 = mk_task("8",
            type=TaskType.EPIC, title="Обновить программу адаптации новичков",
            assignee_id=user_ids["lead.hr"],
            assigned_department_id=depts["HR"],
            start_date=date(2026, 4, 1), due_date=date(2026, 6, 30),
            priority=TaskPriority.MEDIUM, status=TaskStatus.NEW, progress=10,
            created_by=user_ids["admin"],
        )

        # 9. TASK under #8
        t9 = mk_task("9",
            type=TaskType.TASK, title="Подготовить отчёт по найму молодых специалистов",
            parent_id=t8,
            assignee_id=user_ids["anna.hr"],
            assigned_department_id=depts["HR"],
            due_date=date(2026, 5, 30),
            priority=TaskPriority.MEDIUM, status=TaskStatus.IN_PROGRESS, progress=45,
            created_by=user_ids["lead.hr"],
        )

        # 10. SUBTASK (standalone)
        t10 = mk_task("10",
            type=TaskType.SUBTASK, title="Проверить доступы новых сотрудников",
            assignee_id=user_ids["dmitry"],
            assigned_department_id=depts["ИТ"],
            due_date=date(2026, 5, 20),
            priority=TaskPriority.MEDIUM, status=TaskStatus.IN_PROGRESS, progress=30,
            created_by=user_ids["lead.it"],
        )

        # 11. TASK (overdue)
        t11 = mk_task("11",
            type=TaskType.TASK, title="Подготовить отчёт по затратам подразделения",
            assignee_id=user_ids["elena"],
            assigned_department_id=depts["Финансы"],
            start_date=date(2026, 4, 1), due_date=date(2026, 4, 30),
            priority=TaskPriority.HIGH, status=TaskStatus.OVERDUE, progress=20,
            created_by=user_ids["lead.fin"],
        )

        # 12. EPIC
        t12 = mk_task("12",
            type=TaskType.EPIC, title="Внедрить систему мониторинга инфраструктуры",
            assignee_id=user_ids["lead.it"],
            assigned_department_id=depts["ИТ"],
            start_date=date(2026, 4, 1), due_date=date(2026, 6, 30),
            priority=TaskPriority.HIGH, status=TaskStatus.IN_PROGRESS, progress=25,
            created_by=user_ids["admin"],
        )

        # 13. TASK under #12
        t13 = mk_task("13",
            type=TaskType.TASK, title="Развернуть Prometheus + Grafana",
            parent_id=t12,
            assignee_id=user_ids["dmitry"],
            assigned_department_id=depts["ИТ"],
            due_date=date(2026, 5, 31),
            priority=TaskPriority.HIGH, status=TaskStatus.IN_PROGRESS, progress=60,
            created_by=user_ids["lead.it"],
        )

        # 14. TASK
        t14 = mk_task("14",
            type=TaskType.TASK, title="Подготовить квартальный бюджет",
            assignee_id=user_ids["lead.fin"],
            assigned_department_id=depts["Финансы"],
            start_date=date(2026, 6, 1), due_date=date(2026, 6, 30),
            priority=TaskPriority.HIGH, status=TaskStatus.NEW, progress=0,
            created_by=user_ids["admin"],
        )

        # ============================================================
        # Extended demo data: more breadth for dashboards/visualizations
        # ============================================================

        # --- Молодые таланты: дополнительные ветки под GOAL t1 ---
        t15 = mk_task("15",
            type=TaskType.EPIC, title="Запустить программу стажировок",
            parent_id=t1,
            assignee_id=user_ids["lead.talents"],
            assigned_department_id=depts["Молодые таланты"],
            start_date=date(2026, 1, 15), due_date=date(2026, 3, 31),
            priority=TaskPriority.HIGH, status=TaskStatus.DONE, progress=100,
            created_by=user_ids["admin"],
        )
        t16 = mk_task("16",
            type=TaskType.TASK, title="Подготовить материалы для онбординга стажёров",
            parent_id=t15,
            assignee_id=user_ids["pavel"],
            assigned_department_id=depts["Молодые таланты"],
            start_date=date(2026, 2, 1), due_date=date(2026, 2, 28),
            priority=TaskPriority.MEDIUM, status=TaskStatus.DONE, progress=100,
            created_by=user_ids["lead.talents"],
        )
        t17 = mk_task("17",
            type=TaskType.EPIC, title="Карьерный день в МГТУ им. Баумана",
            parent_id=t1,
            assignee_id=user_ids["pavel"],
            assigned_department_id=depts["Молодые таланты"],
            start_date=date(2026, 6, 1), due_date=date(2026, 7, 15),
            priority=TaskPriority.MEDIUM, status=TaskStatus.NEW, progress=0,
            created_by=user_ids["lead.talents"],
        )

        # --- HR: больше задач, перегрузка для Анны ---
        t18 = mk_task("18",
            type=TaskType.TASK, title="Провести интервью на позицию Python-разработчика",
            parent_id=t8,
            assignee_id=user_ids["anna.hr"],
            assigned_department_id=depts["HR"],
            due_date=date(2026, 5, 25),
            priority=TaskPriority.HIGH, status=TaskStatus.IN_PROGRESS, progress=60,
            created_by=user_ids["lead.hr"],
        )
        t19 = mk_task("19",
            type=TaskType.SUBTASK, title="Обновить шаблон трудового договора",
            parent_id=t8,
            assignee_id=user_ids["anna.hr"],
            assigned_department_id=depts["HR"],
            due_date=date(2026, 5, 21),
            priority=TaskPriority.MEDIUM, status=TaskStatus.REVIEW, progress=80,
            created_by=user_ids["lead.hr"],
        )
        t20 = mk_task("20",
            type=TaskType.SUBTASK, title="Подготовить welcome-pack для новых сотрудников",
            assignee_id=user_ids["anna.hr"],
            assigned_department_id=depts["HR"],
            due_date=date(2026, 5, 24),
            priority=TaskPriority.LOW, status=TaskStatus.NEW, progress=0,
            created_by=user_ids["lead.hr"],
        )
        t21 = mk_task("21",
            type=TaskType.TASK, title="Запустить опрос вовлечённости",
            assignee_id=user_ids["anna.hr"],
            assigned_department_id=depts["HR"],
            start_date=date(2026, 5, 15), due_date=date(2026, 6, 15),
            priority=TaskPriority.MEDIUM, status=TaskStatus.IN_PROGRESS, progress=30,
            created_by=user_ids["lead.hr"],
        )
        t22 = mk_task("22",
            type=TaskType.TASK, title="Закрыть позицию руководителя проектов",
            assignee_id=user_ids["lead.hr"],
            assigned_department_id=depts["HR"],
            start_date=date(2026, 3, 1), due_date=date(2026, 4, 15),
            priority=TaskPriority.HIGH, status=TaskStatus.DONE, progress=100,
            created_by=user_ids["admin"],
        )

        # --- ИТ: перегрузка для Дмитрия + завершённые задачи ---
        t23 = mk_task("23",
            type=TaskType.SUBTASK, title="Настроить алёрты в Prometheus",
            parent_id=t13,
            assignee_id=user_ids["dmitry"],
            assigned_department_id=depts["ИТ"],
            due_date=date(2026, 5, 23),
            priority=TaskPriority.HIGH, status=TaskStatus.IN_PROGRESS, progress=40,
            created_by=user_ids["lead.it"],
        )
        t24 = mk_task("24",
            type=TaskType.SUBTASK, title="Построить дашборды по сетевой инфраструктуре",
            parent_id=t13,
            assignee_id=user_ids["dmitry"],
            assigned_department_id=depts["ИТ"],
            due_date=date(2026, 5, 28),
            priority=TaskPriority.MEDIUM, status=TaskStatus.NEW, progress=0,
            created_by=user_ids["lead.it"],
        )
        t25 = mk_task("25",
            type=TaskType.TASK, title="Обновить сертификаты TLS на корпоративных сервисах",
            assignee_id=user_ids["dmitry"],
            assigned_department_id=depts["ИТ"],
            due_date=date(2026, 5, 19),
            priority=TaskPriority.CRITICAL, status=TaskStatus.OVERDUE, progress=70,
            created_by=user_ids["lead.it"],
        )
        t26 = mk_task("26",
            type=TaskType.TASK, title="Мигрировать почтовый сервер на новую версию",
            assignee_id=user_ids["lead.it"],
            assigned_department_id=depts["ИТ"],
            start_date=date(2026, 2, 1), due_date=date(2026, 3, 30),
            priority=TaskPriority.HIGH, status=TaskStatus.DONE, progress=100,
            created_by=user_ids["admin"],
        )
        t27 = mk_task("27",
            type=TaskType.EPIC, title="Аудит безопасности корпоративной сети",
            assignee_id=user_ids["lead.it"],
            assigned_department_id=depts["ИТ"],
            start_date=date(2026, 5, 1), due_date=date(2026, 7, 31),
            priority=TaskPriority.HIGH, status=TaskStatus.IN_PROGRESS, progress=15,
            created_by=user_ids["admin"],
        )

        # --- АХО ---
        t28 = mk_task("28",
            type=TaskType.TASK, title="Закупить мебель для второго этажа",
            assignee_id=user_ids["lead.aho"],
            assigned_department_id=depts["АХО"],
            start_date=date(2026, 4, 15), due_date=date(2026, 5, 15),
            priority=TaskPriority.MEDIUM, status=TaskStatus.OVERDUE, progress=50,
            created_by=user_ids["admin"],
        )
        t29 = mk_task("29",
            type=TaskType.SUBTASK, title="Обновить навигацию по этажам",
            assignee_id=user_ids["alex"],
            assigned_department_id=depts["АХО"],
            due_date=date(2026, 6, 5),
            priority=TaskPriority.LOW, status=TaskStatus.NEW, progress=0,
            created_by=user_ids["lead.aho"],
        )
        t30 = mk_task("30",
            type=TaskType.TASK, title="Организовать корпоратив ко Дню Победы",
            assignee_id=user_ids["alex"],
            assigned_department_id=depts["АХО"],
            start_date=date(2026, 4, 20), due_date=date(2026, 5, 8),
            priority=TaskPriority.HIGH, status=TaskStatus.DONE, progress=100,
            created_by=user_ids["lead.aho"],
        )

        # --- Финансы ---
        t31 = mk_task("31",
            type=TaskType.TASK, title="Согласовать страховой контракт",
            assignee_id=user_ids["elena"],
            assigned_department_id=depts["Финансы"],
            due_date=date(2026, 5, 26),
            priority=TaskPriority.MEDIUM, status=TaskStatus.REVIEW, progress=85,
            created_by=user_ids["lead.fin"],
        )
        t32 = mk_task("32",
            type=TaskType.TASK, title="Подготовить полугодовой отчёт для совета директоров",
            assignee_id=user_ids["lead.fin"],
            assigned_department_id=depts["Финансы"],
            start_date=date(2026, 5, 20), due_date=date(2026, 7, 1),
            priority=TaskPriority.CRITICAL, status=TaskStatus.IN_PROGRESS, progress=10,
            created_by=user_ids["admin"],
        )
        t33 = mk_task("33",
            type=TaskType.SUBTASK, title="Сверить дебиторскую задолженность за апрель",
            assignee_id=user_ids["elena"],
            assigned_department_id=depts["Финансы"],
            due_date=date(2026, 5, 5),
            priority=TaskPriority.MEDIUM, status=TaskStatus.DONE, progress=100,
            created_by=user_ids["lead.fin"],
        )

        # --- Юридический отдел ---
        t34 = mk_task("34",
            type=TaskType.TASK, title="Подготовить NDA для партнёров хакатона",
            assignee_id=user_ids["admin"],  # пока на админе, юр.отдел без выделенного юзера в сиде
            assigned_department_id=depts["Юридический отдел"],
            due_date=date(2026, 5, 21),
            priority=TaskPriority.HIGH, status=TaskStatus.IN_PROGRESS, progress=55,
            created_by=user_ids["admin"],
        )
        t35 = mk_task("35",
            type=TaskType.TASK, title="Проверить условия аренды офиса",
            assigned_department_id=depts["Юридический отдел"],
            start_date=date(2026, 5, 10), due_date=date(2026, 6, 10),
            priority=TaskPriority.MEDIUM, status=TaskStatus.NEW, progress=0,
            created_by=user_ids["admin"],
        )

        # --- Проектный офис ---
        t36 = mk_task("36",
            type=TaskType.EPIC, title="Запустить CRM-портал для клиентов",
            assigned_department_id=depts["Проектный офис"],
            start_date=date(2026, 3, 1), due_date=date(2026, 9, 30),
            priority=TaskPriority.HIGH, status=TaskStatus.IN_PROGRESS, progress=40,
            created_by=user_ids["admin"],
        )
        t37 = mk_task("37",
            type=TaskType.TASK, title="Описать ключевые сценарии CRM",
            parent_id=t36,
            assigned_department_id=depts["Проектный офис"],
            due_date=date(2026, 4, 30),
            priority=TaskPriority.HIGH, status=TaskStatus.DONE, progress=100,
            created_by=user_ids["admin"],
        )
        t38 = mk_task("38",
            type=TaskType.TASK, title="Согласовать интеграцию с 1С",
            parent_id=t36,
            assigned_department_id=depts["Проектный офис"],
            due_date=date(2026, 6, 15),
            priority=TaskPriority.HIGH, status=TaskStatus.IN_PROGRESS, progress=35,
            created_by=user_ids["admin"],
        )

        # --- Дополнительный GOAL (для roadmap) ---
        t39 = mk_task("39",
            type=TaskType.GOAL, title="Сократить издержки на 15% к концу года",
            assignee_id=user_ids["lead.fin"],
            assigned_department_id=depts["Финансы"],
            start_date=date(2026, 1, 1), due_date=date(2026, 12, 31),
            priority=TaskPriority.HIGH, status=TaskStatus.IN_PROGRESS, progress=20,
            created_by=user_ids["admin"],
        )
        t40 = mk_task("40",
            type=TaskType.EPIC, title="Оптимизировать ИТ-расходы",
            parent_id=t39,
            assignee_id=user_ids["lead.it"],
            assigned_department_id=depts["ИТ"],
            start_date=date(2026, 4, 1), due_date=date(2026, 9, 30),
            priority=TaskPriority.MEDIUM, status=TaskStatus.IN_PROGRESS, progress=25,
            created_by=user_ids["lead.fin"],
        )

        # ============================================================
        # Comments на нескольких задачах
        # ============================================================
        def mk_comment(key, task_id, author_key, body):
            db.add(TaskComment(
                id=_id(f"comm-{key}"),
                task_id=task_id,
                author_id=user_ids[author_key],
                body=body,
            ))

        mk_comment("1", t3, "lead.talents",
            "Договорились с организаторами на 22 мая. Нужно срочно согласовать кейс и призовой фонд.")
        mk_comment("2", t3, "pavel",
            "Призовой фонд частично подтвердили со стороны ИТ-партнёров — жду ответ от HR.")
        mk_comment("3", t11, "elena",
            "Задержка из-за того, что не пришли акты от двух подрядчиков. Эскалирую руководителю.")
        mk_comment("4", t11, "lead.fin",
            "Понимаю. Готовлю предварительный вариант на основе имеющихся данных, чтобы не двигать дедлайн ещё дальше.")
        mk_comment("5", t18, "anna.hr",
            "Сегодня провела 3 интервью, два кандидата приглашены на финальный этап.")
        mk_comment("6", t25, "dmitry",
            "Не успеваю сегодня — у меня параллельно горит миграция доступов. Перенесу на завтра утром.")
        mk_comment("7", t25, "lead.it",
            "Это критично — сертификаты уже просрочены. Подключаю в помощь Сергея.")
        mk_comment("8", t36, "admin",
            "Демо для совета директоров запланировано на конец июня. Очень ждём интеграцию с 1С.")

        # ============================================================
        # Расширенная история (status changes, прогресс, делегирование)
        # ============================================================
        now = datetime.now(timezone.utc)

        def mk_history(key, task_id, actor_key, event_type, payload, days_ago=0):
            db.add(TaskHistory(
                id=_id(f"hist2-{key}"),
                task_id=task_id,
                actor_id=user_ids[actor_key] if actor_key else None,
                event_type=event_type,
                payload=payload,
                at=now - timedelta(days=days_ago),
            ))

        mk_history("a1", t2, "lead.talents", "status_changed",
            {"from": "IN_PROGRESS", "to": "REVIEW"}, days_ago=2)
        mk_history("a2", t3, "lead.talents", "progress_updated",
            {"from": 40, "to": 60}, days_ago=1)
        mk_history("a3", t11, None, "status_changed",
            {"from": "IN_PROGRESS", "to": "OVERDUE", "reason": "due_date_passed"}, days_ago=18)
        mk_history("a4", t15, "lead.talents", "status_changed",
            {"from": "REVIEW", "to": "DONE"}, days_ago=45)
        mk_history("a5", t22, "lead.hr", "status_changed",
            {"from": "IN_PROGRESS", "to": "DONE"}, days_ago=30)
        mk_history("a6", t26, "lead.it", "status_changed",
            {"from": "REVIEW", "to": "DONE"}, days_ago=50)
        mk_history("a7", t30, "alex", "status_changed",
            {"from": "IN_PROGRESS", "to": "DONE"}, days_ago=10)
        mk_history("a8", t33, "elena", "status_changed",
            {"from": "IN_PROGRESS", "to": "DONE"}, days_ago=12)
        mk_history("a9", t37, None, "status_changed",
            {"from": "REVIEW", "to": "DONE"}, days_ago=15)
        mk_history("a10", t25, None, "status_changed",
            {"from": "IN_PROGRESS", "to": "OVERDUE", "reason": "due_date_passed"}, days_ago=0)
        mk_history("a11", t28, None, "status_changed",
            {"from": "IN_PROGRESS", "to": "OVERDUE", "reason": "due_date_passed"}, days_ago=4)
        mk_history("a12", t5, "lead.talents", "assignee_changed",
            {"from": None, "to": str(user_ids["pavel"])}, days_ago=7)
        mk_history("a13", t34, "admin", "delegated",
            {"to_department": "Юридический отдел"}, days_ago=5)
        mk_history("a14", t40, "lead.fin", "delegated",
            {"to_department": "ИТ", "assignee": str(user_ids["lead.it"])}, days_ago=3)

        db.commit()
        logger.info("Seed data created successfully.")
    except Exception as e:
        db.rollback()
        logger.error("Seed failed: %s", e)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
