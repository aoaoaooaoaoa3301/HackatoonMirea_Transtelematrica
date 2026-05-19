import enum


class UserRole(str, enum.Enum):
    EMPLOYEE = "EMPLOYEE"
    LEAD = "LEAD"
    ADMIN = "ADMIN"


class TaskType(str, enum.Enum):
    GOAL = "GOAL"
    EPIC = "EPIC"
    TASK = "TASK"
    SUBTASK = "SUBTASK"


class TaskPriority(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class TaskStatus(str, enum.Enum):
    NEW = "NEW"
    IN_PROGRESS = "IN_PROGRESS"
    REVIEW = "REVIEW"
    DONE = "DONE"
    OVERDUE = "OVERDUE"


TASK_TYPE_HIERARCHY = [TaskType.GOAL, TaskType.EPIC, TaskType.TASK, TaskType.SUBTASK]

PRIORITY_WEIGHT = {
    TaskPriority.LOW: 1,
    TaskPriority.MEDIUM: 2,
    TaskPriority.HIGH: 3,
    TaskPriority.CRITICAL: 4,
}
