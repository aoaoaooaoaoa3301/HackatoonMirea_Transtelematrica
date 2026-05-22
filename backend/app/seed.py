"""Idempotent seed script. Creates demo departments, users, and tasks
themed around Транстелематика — a Russian transport telematics company.

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
        # Realistic structure for a transport telematics company
        depts = {
            "Проектный офис": _id("dept-PMO"),
            "НИОКР": _id("dept-RND"),
            "Технический отдел": _id("dept-TECH"),
            "ИТ-инфраструктура": _id("dept-IT"),
            "Производство": _id("dept-PROD"),
            "Тех. поддержка": _id("dept-SUPPORT"),
            "Отдел продаж": _id("dept-SALES"),
            "Финансы": _id("dept-FIN"),
            "HR": _id("dept-HR"),
            "Юридический отдел": _id("dept-LEGAL"),
            "Маркетинг": _id("dept-MKT"),
        }
        for name, did in depts.items():
            db.add(Department(id=did, name=name))
        db.flush()

        # --- Users ---
        users_data = [
            # key, email, full_name, role, dept, skills, seniority
            ("admin", "admin@ttm.local", "Анна Смирнова", UserRole.ADMIN, None, [], None),

            # Leads
            ("lead.pmo", "lead.pmo@ttm.local", "Иван Петров", UserRole.LEAD, "Проектный офис", ["внедрение", "АСУ ОТ", "региональные проекты"], "senior"),
            ("lead.rnd", "lead.rnd@ttm.local", "Сергей Кузнецов", UserRole.LEAD, "НИОКР", ["embedded", "ГЛОНАСС", "БортКомп", "C/C++"], "senior"),
            ("lead.tech", "lead.tech@ttm.local", "Михаил Воронов", UserRole.LEAD, "Технический отдел", ["backend", "архитектура", "telematics"], "senior"),
            ("lead.it", "lead.it@ttm.local", "Дмитрий Орлов", UserRole.LEAD, "ИТ-инфраструктура", ["devops", "kubernetes", "мониторинг"], "senior"),
            ("lead.prod", "lead.prod@ttm.local", "Виктор Зайцев", UserRole.LEAD, "Производство", ["производство", "qa", "сертификация"], "senior"),
            ("lead.support", "lead.support@ttm.local", "Ольга Иванова", UserRole.LEAD, "Тех. поддержка", ["клиенты", "перевозчики", "SLA"], "senior"),
            ("lead.sales", "lead.sales@ttm.local", "Андрей Соколов", UserRole.LEAD, "Отдел продаж", ["B2B", "тендеры", "региональные клиенты"], "senior"),
            ("lead.fin", "lead.fin@ttm.local", "Татьяна Зайцева", UserRole.LEAD, "Финансы", ["отчётность", "бюджет", "ФСБУ"], "senior"),
            ("lead.hr", "lead.hr@ttm.local", "Мария Соколова", UserRole.LEAD, "HR", ["найм", "адаптация", "ИТ-рекрутинг"], "senior"),
            ("lead.mkt", "lead.mkt@ttm.local", "Екатерина Белова", UserRole.LEAD, "Маркетинг", ["b2b-маркетинг", "выставки", "контент"], "middle"),
            ("lead.legal", "lead.legal@ttm.local", "Наталья Морозова", UserRole.LEAD, "Юридический отдел", ["договорное право", "287-ФЗ", "комплаенс", "тендеры"], "senior"),

            # Engineers / employees
            ("dev.alex", "alex@ttm.local", "Алексей Новиков", UserRole.EMPLOYEE, "Технический отдел", ["python", "fastapi", "postgresql"], "middle"),
            ("dev.pavel", "pavel@ttm.local", "Павел Соловьёв", UserRole.EMPLOYEE, "НИОКР", ["embedded", "stm32", "can-bus"], "junior"),
            ("dev.dmitry", "dmitry@ttm.local", "Дмитрий Лебедев", UserRole.EMPLOYEE, "ИТ-инфраструктура", ["k8s", "ansible", "prometheus"], "middle"),
            ("dev.nikita", "nikita@ttm.local", "Никита Морозов", UserRole.EMPLOYEE, "Технический отдел", ["python", "kafka", "telematics-protocols"], "middle"),
            ("support.elena", "elena@ttm.local", "Елена Васильева", UserRole.EMPLOYEE, "Тех. поддержка", ["саппорт", "перевозчики", "АСУ ОТ"], "middle"),
            ("support.roman", "roman@ttm.local", "Роман Григорьев", UserRole.EMPLOYEE, "Тех. поддержка", ["диагностика", "БортКомп"], "junior"),
            ("hr.anna", "anna.hr@ttm.local", "Анна Лебедева", UserRole.EMPLOYEE, "HR", ["ИТ-рекрутинг", "онбординг"], "middle"),
            ("fin.olga", "olga.fin@ttm.local", "Ольга Кузьмина", UserRole.EMPLOYEE, "Финансы", ["1С", "отчётность"], "middle"),
            ("sales.kirill", "kirill@ttm.local", "Кирилл Денисов", UserRole.EMPLOYEE, "Отдел продаж", ["B2B", "тендеры"], "middle"),
            ("prod.igor", "igor@ttm.local", "Игорь Семёнов", UserRole.EMPLOYEE, "Производство", ["сборка", "пайка", "qa"], "middle"),
            ("legal.sergey", "sergey.legal@ttm.local", "Сергей Волков", UserRole.EMPLOYEE, "Юридический отдел", ["договоры", "лицензирование"], "middle"),
            ("legal.maria", "maria.legal@ttm.local", "Мария Зотова", UserRole.EMPLOYEE, "Юридический отдел", ["комплаенс", "287-ФЗ"], "junior"),

            # Memorable demo accounts shown on the login screen (so the roles
            # can actually be tried: lead@ = Руководитель, user@ = Сотрудник).
            ("demo.lead", "lead@ttm.local", "Олег Демидов", UserRole.LEAD, "Технический отдел", ["управление", "telematics", "архитектура"], "senior"),
            ("demo.user", "user@ttm.local", "Степан Орехов", UserRole.EMPLOYEE, "Технический отдел", ["python", "qa"], "middle"),
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
            "Проектный офис": "lead.pmo",
            "НИОКР": "lead.rnd",
            "Технический отдел": "lead.tech",
            "ИТ-инфраструктура": "lead.it",
            "Производство": "lead.prod",
            "Тех. поддержка": "lead.support",
            "Отдел продаж": "lead.sales",
            "Финансы": "lead.fin",
            "HR": "lead.hr",
            "Маркетинг": "lead.mkt",
            "Юридический отдел": "lead.legal",
        }
        for dept_name, user_key in head_map.items():
            dept = db.get(Department, depts[dept_name])
            dept.head_user_id = user_ids[user_key]
        db.flush()

        # --- Tasks ---
        admin_id = user_ids["admin"]

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

        # ============================================================
        # GOAL 1: Регионы — стратегическая цель года
        # ============================================================
        t1 = mk_task("1",
            type=TaskType.GOAL, title="Развернуть телематический комплекс в 5 регионах РФ",
            description="Внедрение АСУ ОТ и подключение муниципальных перевозчиков в Казани, Нижнем Новгороде, Перми, Воронеже и Краснодаре до конца года.",
            assignee_id=user_ids["lead.pmo"],
            assigned_department_id=depts["Проектный офис"],
            start_date=date(2026, 1, 1), due_date=date(2026, 12, 31),
            priority=TaskPriority.CRITICAL, status=TaskStatus.IN_PROGRESS, progress=42,
            created_by=user_ids["admin"],
        )
        t2 = mk_task("2",
            type=TaskType.EPIC, title="Внедрение АСУ ОТ в Казани",
            description="Подключить городского перевозчика к диспетчерской системе, развернуть БортКомп v3 на 850 автобусах.",
            parent_id=t1,
            assignee_id=user_ids["lead.pmo"],
            assigned_department_id=depts["Проектный офис"],
            start_date=date(2026, 4, 1), due_date=date(2026, 6, 30),
            priority=TaskPriority.HIGH, status=TaskStatus.IN_PROGRESS, progress=65,
            created_by=user_ids["admin"],
        )
        t3 = mk_task("3",
            type=TaskType.TASK, title="Подключить 850 автобусов к диспетчерской",
            description="Установка БортКомп, конфигурация SIM-карт, регистрация в АСУ ОТ.",
            parent_id=t2,
            assignee_id=user_ids["dev.nikita"],
            assigned_department_id=depts["Технический отдел"],
            start_date=date(2026, 5, 1), due_date=date(2026, 5, 31),
            priority=TaskPriority.HIGH, status=TaskStatus.IN_PROGRESS, progress=72,
            created_by=user_ids["lead.pmo"],
        )
        t4 = mk_task("4",
            type=TaskType.SUBTASK, title="Согласовать схему интеграции с региональной ИИС",
            parent_id=t3,
            assignee_id=user_ids["lead.tech"],
            assigned_department_id=depts["Технический отдел"],
            due_date=date(2026, 5, 22),
            priority=TaskPriority.HIGH, status=TaskStatus.REVIEW, progress=85,
            created_by=user_ids["lead.pmo"],
        )
        t5 = mk_task("5",
            type=TaskType.SUBTASK, title="Провести обучение диспетчеров перевозчика",
            parent_id=t3,
            assignee_id=user_ids["support.elena"],
            assigned_department_id=depts["Тех. поддержка"],
            due_date=date(2026, 5, 25),
            priority=TaskPriority.MEDIUM, status=TaskStatus.IN_PROGRESS, progress=40,
            created_by=user_ids["lead.support"],
        )
        t6 = mk_task("6",
            type=TaskType.EPIC, title="Подключить 1500 автобусов в Нижнем Новгороде",
            parent_id=t1,
            assignee_id=user_ids["lead.pmo"],
            assigned_department_id=depts["Проектный офис"],
            start_date=date(2026, 5, 10), due_date=date(2026, 9, 30),
            priority=TaskPriority.HIGH, status=TaskStatus.NEW, progress=5,
            created_by=user_ids["admin"],
        )
        t7 = mk_task("7",
            type=TaskType.EPIC, title="Сертификация комплекса по 287-ФЗ",
            description="Прохождение сертификации соответствия требованиям 287-ФЗ «О национальной системе пространственных данных».",
            parent_id=t1,
            assignee_id=user_ids["lead.prod"],
            assigned_department_id=depts["Производство"],
            start_date=date(2026, 3, 1), due_date=date(2026, 7, 31),
            priority=TaskPriority.CRITICAL, status=TaskStatus.IN_PROGRESS, progress=55,
            created_by=user_ids["admin"],
        )
        t8 = mk_task("8",
            type=TaskType.SUBTASK, title="Подготовить пакет документации для ФСТЭК",
            parent_id=t7,
            assignee_id=user_ids["admin"],
            assigned_department_id=depts["Юридический отдел"],
            due_date=date(2026, 5, 23),
            priority=TaskPriority.HIGH, status=TaskStatus.IN_PROGRESS, progress=60,
            created_by=user_ids["lead.prod"],
        )

        # ============================================================
        # GOAL 2: Новое поколение БортКомп v4
        # ============================================================
        t9 = mk_task("9",
            type=TaskType.GOAL, title="Запустить новое поколение БортКомп v4",
            description="Разработать, протестировать и вывести в серию бортовой компьютер v4 на отечественном процессоре.",
            assignee_id=user_ids["lead.rnd"],
            assigned_department_id=depts["НИОКР"],
            start_date=date(2026, 1, 1), due_date=date(2026, 12, 31),
            priority=TaskPriority.HIGH, status=TaskStatus.IN_PROGRESS, progress=38,
            created_by=user_ids["admin"],
        )
        t10 = mk_task("10",
            type=TaskType.EPIC, title="Прототип БортКомп v4 на новом процессоре",
            parent_id=t9,
            assignee_id=user_ids["lead.rnd"],
            assigned_department_id=depts["НИОКР"],
            start_date=date(2026, 2, 1), due_date=date(2026, 6, 30),
            priority=TaskPriority.HIGH, status=TaskStatus.IN_PROGRESS, progress=70,
            created_by=user_ids["admin"],
        )
        t11 = mk_task("11",
            type=TaskType.TASK, title="Разработать прошивку для нового процессора",
            parent_id=t10,
            assignee_id=user_ids["dev.pavel"],
            assigned_department_id=depts["НИОКР"],
            start_date=date(2026, 3, 1), due_date=date(2026, 6, 15),
            priority=TaskPriority.HIGH, status=TaskStatus.IN_PROGRESS, progress=55,
            created_by=user_ids["lead.rnd"],
        )
        t12 = mk_task("12",
            type=TaskType.SUBTASK, title="Реализовать драйвер CAN-bus",
            parent_id=t11,
            assignee_id=user_ids["dev.pavel"],
            assigned_department_id=depts["НИОКР"],
            due_date=date(2026, 5, 26),
            priority=TaskPriority.HIGH, status=TaskStatus.IN_PROGRESS, progress=70,
            created_by=user_ids["lead.rnd"],
        )
        t13 = mk_task("13",
            type=TaskType.EPIC, title="Лабораторные тесты в условиях -40°C ... +85°C",
            parent_id=t9,
            assignee_id=user_ids["lead.prod"],
            assigned_department_id=depts["Производство"],
            start_date=date(2026, 5, 15), due_date=date(2026, 8, 31),
            priority=TaskPriority.HIGH, status=TaskStatus.NEW, progress=0,
            created_by=user_ids["lead.rnd"],
        )

        # ============================================================
        # GOAL 3: Финансовая оптимизация
        # ============================================================
        t14 = mk_task("14",
            type=TaskType.GOAL, title="Сократить TCO эксплуатации на 20%",
            description="Снизить совокупную стоимость владения для текущих клиентов за счёт оптимизации SIM-тарифов, миграции на собственный ЦОД и автоматизации поддержки.",
            assignee_id=user_ids["lead.fin"],
            assigned_department_id=depts["Финансы"],
            start_date=date(2026, 1, 1), due_date=date(2026, 12, 31),
            priority=TaskPriority.HIGH, status=TaskStatus.IN_PROGRESS, progress=25,
            created_by=user_ids["admin"],
        )
        t15 = mk_task("15",
            type=TaskType.EPIC, title="Миграция диспетчерской на собственный ЦОД",
            parent_id=t14,
            assignee_id=user_ids["lead.it"],
            assigned_department_id=depts["ИТ-инфраструктура"],
            start_date=date(2026, 4, 1), due_date=date(2026, 9, 30),
            priority=TaskPriority.HIGH, status=TaskStatus.IN_PROGRESS, progress=35,
            created_by=user_ids["lead.fin"],
        )
        t16 = mk_task("16",
            type=TaskType.TASK, title="Развернуть Kubernetes-кластер в собственном ЦОД",
            parent_id=t15,
            assignee_id=user_ids["dev.dmitry"],
            assigned_department_id=depts["ИТ-инфраструктура"],
            due_date=date(2026, 5, 30),
            priority=TaskPriority.HIGH, status=TaskStatus.IN_PROGRESS, progress=65,
            created_by=user_ids["lead.it"],
        )
        t17 = mk_task("17",
            type=TaskType.SUBTASK, title="Настроить мониторинг Prometheus + Grafana",
            parent_id=t16,
            assignee_id=user_ids["dev.dmitry"],
            assigned_department_id=depts["ИТ-инфраструктура"],
            due_date=date(2026, 5, 24),
            priority=TaskPriority.MEDIUM, status=TaskStatus.IN_PROGRESS, progress=40,
            created_by=user_ids["lead.it"],
        )

        # ============================================================
        # OVERDUE и at-risk tasks
        # ============================================================
        t18 = mk_task("18",
            type=TaskType.TASK, title="Обновить TLS-сертификаты на API-шлюзах",
            description="Срочно: продлить сертификаты Let's Encrypt на api.transtelematica.ru и dispatch.transtelematica.ru.",
            assignee_id=user_ids["dev.dmitry"],
            assigned_department_id=depts["ИТ-инфраструктура"],
            due_date=date(2026, 5, 17),  # in past
            priority=TaskPriority.CRITICAL, status=TaskStatus.OVERDUE, progress=70,
            created_by=user_ids["lead.it"],
        )
        t19 = mk_task("19",
            type=TaskType.TASK, title="Подготовить отчёт по затратам подразделения за апрель",
            description="Ежемесячный отчёт по затратам Технического отдела для финансовой дирекции.",
            assignee_id=user_ids["fin.olga"],
            assigned_department_id=depts["Финансы"],
            start_date=date(2026, 4, 15), due_date=date(2026, 5, 5),
            priority=TaskPriority.HIGH, status=TaskStatus.OVERDUE, progress=30,
            created_by=user_ids["lead.fin"],
        )
        t20 = mk_task("20",
            type=TaskType.TASK, title="Заменить парк бортовых модемов в Перми",
            description="2G-сети отключаются, нужно заменить 320 устаревших модемов на 4G.",
            assignee_id=user_ids["support.roman"],
            assigned_department_id=depts["Тех. поддержка"],
            start_date=date(2026, 3, 20), due_date=date(2026, 5, 15),
            priority=TaskPriority.HIGH, status=TaskStatus.OVERDUE, progress=55,
            created_by=user_ids["lead.support"],
        )

        # ============================================================
        # HR
        # ============================================================
        t21 = mk_task("21",
            type=TaskType.EPIC, title="Закрыть 5 ключевых ИТ-позиций до конца квартала",
            assignee_id=user_ids["lead.hr"],
            assigned_department_id=depts["HR"],
            start_date=date(2026, 4, 1), due_date=date(2026, 6, 30),
            priority=TaskPriority.HIGH, status=TaskStatus.IN_PROGRESS, progress=50,
            created_by=user_ids["admin"],
        )
        t22 = mk_task("22",
            type=TaskType.TASK, title="Провести интервью на embedded-разработчика",
            parent_id=t21,
            assignee_id=user_ids["hr.anna"],
            assigned_department_id=depts["HR"],
            due_date=date(2026, 5, 23),
            priority=TaskPriority.HIGH, status=TaskStatus.IN_PROGRESS, progress=60,
            created_by=user_ids["lead.hr"],
        )
        t23 = mk_task("23",
            type=TaskType.TASK, title="Закрыть позицию DevOps-инженера",
            parent_id=t21,
            assignee_id=user_ids["hr.anna"],
            assigned_department_id=depts["HR"],
            due_date=date(2026, 6, 10),
            priority=TaskPriority.MEDIUM, status=TaskStatus.IN_PROGRESS, progress=45,
            created_by=user_ids["lead.hr"],
        )
        t24 = mk_task("24",
            type=TaskType.SUBTASK, title="Подготовить welcome-pack для новых разработчиков",
            assignee_id=user_ids["hr.anna"],
            assigned_department_id=depts["HR"],
            due_date=date(2026, 5, 28),
            priority=TaskPriority.LOW, status=TaskStatus.NEW, progress=0,
            created_by=user_ids["lead.hr"],
        )
        t25 = mk_task("25",
            type=TaskType.TASK, title="Запустить программу адаптации стажёров летнего набора",
            assignee_id=user_ids["lead.hr"],
            assigned_department_id=depts["HR"],
            start_date=date(2026, 5, 1), due_date=date(2026, 6, 30),
            priority=TaskPriority.MEDIUM, status=TaskStatus.IN_PROGRESS, progress=30,
            created_by=user_ids["admin"],
        )

        # ============================================================
        # Sales / Тендеры
        # ============================================================
        t26 = mk_task("26",
            type=TaskType.EPIC, title="Выиграть тендер Минтранса на 2026-2028",
            description="Тендер на поставку АСУ ОТ для 12 регионов РФ.",
            assignee_id=user_ids["lead.sales"],
            assigned_department_id=depts["Отдел продаж"],
            start_date=date(2026, 4, 1), due_date=date(2026, 7, 15),
            priority=TaskPriority.CRITICAL, status=TaskStatus.IN_PROGRESS, progress=40,
            created_by=user_ids["admin"],
        )
        t27 = mk_task("27",
            type=TaskType.TASK, title="Подготовить тендерную документацию",
            parent_id=t26,
            assignee_id=user_ids["sales.kirill"],
            assigned_department_id=depts["Отдел продаж"],
            due_date=date(2026, 5, 30),
            priority=TaskPriority.CRITICAL, status=TaskStatus.IN_PROGRESS, progress=55,
            created_by=user_ids["lead.sales"],
        )
        t28 = mk_task("28",
            type=TaskType.SUBTASK, title="Согласовать ценовое предложение с финансовым отделом",
            parent_id=t27,
            assignee_id=user_ids["lead.fin"],
            assigned_department_id=depts["Финансы"],
            due_date=date(2026, 5, 24),
            priority=TaskPriority.HIGH, status=TaskStatus.REVIEW, progress=85,
            created_by=user_ids["lead.sales"],
        )
        t29 = mk_task("29",
            type=TaskType.TASK, title="Подписать пилотный договор с Москва-Транс",
            assignee_id=user_ids["lead.sales"],
            assigned_department_id=depts["Отдел продаж"],
            start_date=date(2026, 5, 5), due_date=date(2026, 6, 5),
            priority=TaskPriority.HIGH, status=TaskStatus.IN_PROGRESS, progress=70,
            created_by=user_ids["admin"],
        )

        # ============================================================
        # Производство
        # ============================================================
        t30 = mk_task("30",
            type=TaskType.TASK, title="Собрать опытную партию БортКомп v4 (50 шт)",
            assignee_id=user_ids["prod.igor"],
            assigned_department_id=depts["Производство"],
            start_date=date(2026, 5, 15), due_date=date(2026, 6, 20),
            priority=TaskPriority.HIGH, status=TaskStatus.NEW, progress=10,
            created_by=user_ids["lead.prod"],
        )
        t31 = mk_task("31",
            type=TaskType.TASK, title="Закупить новые SMD-компоненты для серийной партии",
            assignee_id=user_ids["lead.prod"],
            assigned_department_id=depts["Производство"],
            due_date=date(2026, 5, 27),
            priority=TaskPriority.MEDIUM, status=TaskStatus.IN_PROGRESS, progress=50,
            created_by=user_ids["admin"],
        )

        # ============================================================
        # Тех.поддержка / клиенты
        # ============================================================
        t32 = mk_task("32",
            type=TaskType.EPIC, title="Снизить среднее время решения тикетов до 4ч",
            assignee_id=user_ids["lead.support"],
            assigned_department_id=depts["Тех. поддержка"],
            start_date=date(2026, 4, 1), due_date=date(2026, 9, 30),
            priority=TaskPriority.MEDIUM, status=TaskStatus.IN_PROGRESS, progress=35,
            created_by=user_ids["admin"],
        )
        t33 = mk_task("33",
            type=TaskType.TASK, title="Обновить базу знаний по типовым неисправностям БортКомп v3",
            parent_id=t32,
            assignee_id=user_ids["support.elena"],
            assigned_department_id=depts["Тех. поддержка"],
            due_date=date(2026, 5, 31),
            priority=TaskPriority.MEDIUM, status=TaskStatus.IN_PROGRESS, progress=60,
            created_by=user_ids["lead.support"],
        )
        t34 = mk_task("34",
            type=TaskType.TASK, title="Внедрить интеграцию тикет-системы с диспетчерской",
            parent_id=t32,
            assignee_id=user_ids["dev.alex"],
            assigned_department_id=depts["Технический отдел"],
            due_date=date(2026, 6, 30),
            priority=TaskPriority.MEDIUM, status=TaskStatus.NEW, progress=0,
            created_by=user_ids["lead.support"],
        )

        # ============================================================
        # Маркетинг
        # ============================================================
        t35 = mk_task("35",
            type=TaskType.TASK, title="Подготовить стенд для выставки «Транспортная неделя»",
            assignee_id=user_ids["lead.mkt"],
            assigned_department_id=depts["Маркетинг"],
            start_date=date(2026, 5, 15), due_date=date(2026, 6, 20),
            priority=TaskPriority.MEDIUM, status=TaskStatus.IN_PROGRESS, progress=25,
            created_by=user_ids["admin"],
        )
        t36 = mk_task("36",
            type=TaskType.SUBTASK, title="Согласовать дизайн-макет стенда",
            parent_id=t35,
            assignee_id=user_ids["lead.mkt"],
            assigned_department_id=depts["Маркетинг"],
            due_date=date(2026, 5, 26),
            priority=TaskPriority.MEDIUM, status=TaskStatus.REVIEW, progress=80,
            created_by=user_ids["lead.mkt"],
        )
        t37 = mk_task("37",
            type=TaskType.TASK, title="Обновить корпоративный сайт — раздел «Решения»",
            assignee_id=user_ids["lead.mkt"],
            assigned_department_id=depts["Маркетинг"],
            due_date=date(2026, 6, 15),
            priority=TaskPriority.LOW, status=TaskStatus.NEW, progress=0,
            created_by=user_ids["admin"],
        )

        # ============================================================
        # Юридический отдел
        # ============================================================
        t38 = mk_task("38",
            type=TaskType.TASK, title="Согласовать NDA с подрядчиками по тендеру Минтранса",
            assignee_id=user_ids["lead.legal"],
            assigned_department_id=depts["Юридический отдел"],
            due_date=date(2026, 5, 22),
            priority=TaskPriority.HIGH, status=TaskStatus.IN_PROGRESS, progress=50,
            created_by=user_ids["lead.sales"],
        )
        t39 = mk_task("39",
            type=TaskType.TASK, title="Подготовить договор поставки для Казанского перевозчика",
            assignee_id=user_ids["legal.sergey"],
            assigned_department_id=depts["Юридический отдел"],
            due_date=date(2026, 5, 29),
            priority=TaskPriority.HIGH, status=TaskStatus.NEW, progress=0,
            created_by=user_ids["lead.sales"],
        )

        # ============================================================
        # Завершённые задачи (для completion-rate и истории)
        # ============================================================
        t40 = mk_task("40",
            type=TaskType.EPIC, title="Миграция почтового сервера на отечественное ПО",
            assignee_id=user_ids["lead.it"],
            assigned_department_id=depts["ИТ-инфраструктура"],
            start_date=date(2026, 2, 1), due_date=date(2026, 3, 31),
            priority=TaskPriority.HIGH, status=TaskStatus.DONE, progress=100,
            created_by=user_ids["admin"],
        )
        t41 = mk_task("41",
            type=TaskType.TASK, title="Развернуть систему резервного копирования в холодном ЦОД",
            assignee_id=user_ids["dev.dmitry"],
            assigned_department_id=depts["ИТ-инфраструктура"],
            start_date=date(2026, 3, 1), due_date=date(2026, 4, 15),
            priority=TaskPriority.HIGH, status=TaskStatus.DONE, progress=100,
            created_by=user_ids["lead.it"],
        )
        t42 = mk_task("42",
            type=TaskType.TASK, title="Подписать договор с Казанским метрополитеном",
            assignee_id=user_ids["lead.sales"],
            assigned_department_id=depts["Отдел продаж"],
            due_date=date(2026, 4, 25),
            priority=TaskPriority.HIGH, status=TaskStatus.DONE, progress=100,
            created_by=user_ids["admin"],
        )
        t43 = mk_task("43",
            type=TaskType.TASK, title="Закрыть позицию руководителя НИОКР",
            assignee_id=user_ids["lead.hr"],
            assigned_department_id=depts["HR"],
            due_date=date(2026, 4, 10),
            priority=TaskPriority.CRITICAL, status=TaskStatus.DONE, progress=100,
            created_by=user_ids["admin"],
        )
        t44 = mk_task("44",
            type=TaskType.TASK, title="Сверить дебиторскую задолженность за март",
            assignee_id=user_ids["fin.olga"],
            assigned_department_id=depts["Финансы"],
            due_date=date(2026, 4, 5),
            priority=TaskPriority.MEDIUM, status=TaskStatus.DONE, progress=100,
            created_by=user_ids["lead.fin"],
        )
        t45 = mk_task("45",
            type=TaskType.TASK, title="Провести квартальную инвентаризацию складских остатков",
            assignee_id=user_ids["lead.prod"],
            assigned_department_id=depts["Производство"],
            due_date=date(2026, 4, 20),
            priority=TaskPriority.MEDIUM, status=TaskStatus.DONE, progress=100,
            created_by=user_ids["admin"],
        )

        # ============================================================
        # Comments на горячих задачах
        # ============================================================
        def mk_comment(key, task_id, author_key, body):
            db.add(TaskComment(
                id=_id(f"comm-{key}"),
                task_id=task_id,
                author_id=user_ids[author_key],
                body=body,
            ))

        mk_comment("1", t3, "lead.pmo",
            "Согласовали с Казанью график подключения. Установка идёт с опережением — 720 из 850 авто уже подключены.")
        mk_comment("2", t3, "dev.nikita",
            "Есть нюанс по интеграции с региональной ИИС — нужно обновить формат экспорта. Жду от технического отдела.")
        mk_comment("3", t18, "dev.dmitry",
            "Не успеваю сегодня — горит миграция доступов к ЦОД. Перенесу на завтра утром.")
        mk_comment("4", t18, "lead.it",
            "Сертификаты уже просрочены, это блокирует прод. Подключаю Никиту в помощь.")
        mk_comment("5", t19, "fin.olga",
            "Задержка из-за того, что не пришли первичные документы от двух подрядчиков. Эскалирую.")
        mk_comment("6", t20, "support.roman",
            "Партия модемов застряла на таможне. Логистика обещает разрулить до конца недели.")
        mk_comment("7", t22, "hr.anna",
            "Сегодня провела 3 интервью, двое кандидатов с опытом STM32 приглашены на финал.")
        mk_comment("8", t27, "sales.kirill",
            "Финансы согласовали цены, готовлю финальную версию ТКП на завтра.")
        mk_comment("9", t12, "dev.pavel",
            "Базовая реализация CAN-bus драйвера готова, начал интеграционные тесты.")
        mk_comment("10", t8, "admin",
            "Юристы запрашивают дополнительный пакет техдокументации — передал Сергею Кузнецову.")

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

        mk_history("a1", t3, "dev.nikita", "progress_updated",
            {"from": 50, "to": 72}, days_ago=1)
        mk_history("a2", t4, "lead.tech", "status_changed",
            {"from": "IN_PROGRESS", "to": "REVIEW"}, days_ago=2)
        mk_history("a3", t18, None, "status_changed",
            {"from": "IN_PROGRESS", "to": "OVERDUE", "reason": "due_date_passed"}, days_ago=2)
        mk_history("a4", t19, None, "status_changed",
            {"from": "IN_PROGRESS", "to": "OVERDUE", "reason": "due_date_passed"}, days_ago=14)
        mk_history("a5", t20, None, "status_changed",
            {"from": "IN_PROGRESS", "to": "OVERDUE", "reason": "due_date_passed"}, days_ago=4)
        mk_history("a6", t40, "lead.it", "status_changed",
            {"from": "REVIEW", "to": "DONE"}, days_ago=50)
        mk_history("a7", t41, "dev.dmitry", "status_changed",
            {"from": "IN_PROGRESS", "to": "DONE"}, days_ago=35)
        mk_history("a8", t42, "lead.sales", "status_changed",
            {"from": "REVIEW", "to": "DONE"}, days_ago=25)
        mk_history("a9", t43, "lead.hr", "status_changed",
            {"from": "IN_PROGRESS", "to": "DONE"}, days_ago=40)
        mk_history("a10", t44, "fin.olga", "status_changed",
            {"from": "IN_PROGRESS", "to": "DONE"}, days_ago=44)
        mk_history("a11", t45, "lead.prod", "status_changed",
            {"from": "IN_PROGRESS", "to": "DONE"}, days_ago=30)
        mk_history("a12", t36, "lead.mkt", "status_changed",
            {"from": "IN_PROGRESS", "to": "REVIEW"}, days_ago=1)
        mk_history("a13", t28, "lead.fin", "status_changed",
            {"from": "IN_PROGRESS", "to": "REVIEW"}, days_ago=2)
        mk_history("a14", t38, "admin", "delegated",
            {"to_department": "Юридический отдел"}, days_ago=5)
        mk_history("a15", t15, "lead.fin", "delegated",
            {"to_department": "ИТ-инфраструктура", "assignee": str(user_ids["lead.it"])}, days_ago=10)
        mk_history("a16", t11, "dev.pavel", "progress_updated",
            {"from": 30, "to": 55}, days_ago=3)
        mk_history("a17", t29, "lead.sales", "progress_updated",
            {"from": 40, "to": 70}, days_ago=2)

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
