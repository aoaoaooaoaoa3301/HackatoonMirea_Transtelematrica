"""Idempotent seed script. Creates demo departments, users, and tasks.

Uses uuid5 with a fixed namespace so IDs are deterministic across runs.
"""
import logging
import uuid
from datetime import date

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models.department import Department
from app.models.user import User
from app.models.task import Task, TaskHistory
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
