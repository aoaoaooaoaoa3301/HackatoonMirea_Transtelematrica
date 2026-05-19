import type { Status, Priority, TaskType, Role } from '@/types';

export const STATUS_LABELS: Record<Status, string> = {
  NEW: 'Новая',
  IN_PROGRESS: 'В работе',
  REVIEW: 'На согласовании',
  DONE: 'Выполнена',
  OVERDUE: 'Просрочена',
};

export const STATUS_COLORS: Record<Status, { text: string; bg: string; dot: string }> = {
  NEW: { text: 'text-violet-700 dark:text-violet-300', bg: 'bg-violet-100 dark:bg-violet-900/40', dot: 'bg-violet-500' },
  IN_PROGRESS: { text: 'text-blue-700 dark:text-blue-300', bg: 'bg-blue-100 dark:bg-blue-900/40', dot: 'bg-blue-500' },
  REVIEW: { text: 'text-cyan-700 dark:text-cyan-300', bg: 'bg-cyan-100 dark:bg-cyan-900/40', dot: 'bg-cyan-500' },
  DONE: { text: 'text-emerald-700 dark:text-emerald-300', bg: 'bg-emerald-100 dark:bg-emerald-900/40', dot: 'bg-emerald-500' },
  OVERDUE: { text: 'text-rose-700 dark:text-rose-300', bg: 'bg-rose-100 dark:bg-rose-900/40', dot: 'bg-rose-500' },
};

/** Display-only "at risk" style for tasks near due date but not yet done/overdue */
export const AT_RISK_STYLE = {
  label: 'Риск срыва',
  text: 'text-amber-700 dark:text-amber-300',
  bg: 'bg-amber-100 dark:bg-amber-900/40',
  dot: 'bg-amber-500',
};

/** Check if a task is visually "at risk": due within 3 days and not DONE/OVERDUE */
export function isAtRisk(dueDate: string | null | undefined, status: Status): boolean {
  if (!dueDate || status === 'DONE' || status === 'OVERDUE') return false;
  const due = new Date(dueDate);
  const now = new Date();
  const diffMs = due.getTime() - now.getTime();
  const diffDays = diffMs / (1000 * 60 * 60 * 24);
  return diffDays >= 0 && diffDays <= 3;
}

export const STATUS_CHART_COLORS: Record<Status, string> = {
  NEW: '#8B5CF6',
  IN_PROGRESS: '#3B82F6',
  REVIEW: '#06B6D4',
  DONE: '#10B981',
  OVERDUE: '#EF4444',
};

export const PRIORITY_LABELS: Record<Priority, string> = {
  LOW: 'Низкий',
  MEDIUM: 'Средний',
  HIGH: 'Высокий',
  CRITICAL: 'Критический',
};

export const PRIORITY_COLORS: Record<Priority, { text: string; bg: string }> = {
  LOW: { text: 'text-slate-600 dark:text-slate-400', bg: 'bg-slate-100 dark:bg-slate-800' },
  MEDIUM: { text: 'text-sky-700 dark:text-sky-300', bg: 'bg-sky-100 dark:bg-sky-900/40' },
  HIGH: { text: 'text-orange-700 dark:text-orange-300', bg: 'bg-orange-100 dark:bg-orange-900/40' },
  CRITICAL: { text: 'text-red-700 dark:text-red-300', bg: 'bg-red-100 dark:bg-red-900/40' },
};

export const TASK_TYPE_LABELS: Record<TaskType, string> = {
  GOAL: 'Цель',
  EPIC: 'Эпик',
  TASK: 'Задача',
  SUBTASK: 'Подзадача',
};

export const ROLE_LABELS: Record<Role, string> = {
  EMPLOYEE: 'Сотрудник',
  LEAD: 'Руководитель',
  ADMIN: 'Администратор',
};

export const ALL_STATUSES: Status[] = ['NEW', 'IN_PROGRESS', 'REVIEW', 'DONE', 'OVERDUE'];
export const ALL_PRIORITIES: Priority[] = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'];
export const ALL_TASK_TYPES: TaskType[] = ['GOAL', 'EPIC', 'TASK', 'SUBTASK'];
export const ALL_PERIOD_BUCKETS = ['year', 'quarter', 'month', 'week'] as const;

export const PERIOD_LABELS: Record<string, string> = {
  year: 'Год',
  quarter: 'Квартал',
  month: 'Месяц',
  week: 'Неделя',
};

export function getCapacityColor(util: number): string {
  if (util > 120) return 'text-rose-600 dark:text-rose-400';
  if (util > 80) return 'text-amber-600 dark:text-amber-400';
  return 'text-emerald-600 dark:text-emerald-400';
}

export function getCapacityBgColor(util: number): string {
  if (util > 120) return 'bg-rose-500';
  if (util > 80) return 'bg-amber-500';
  return 'bg-emerald-500';
}
