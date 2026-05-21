import type { User } from '@/types';

/**
 * Frontend permission helpers — mirror the backend RBAC rules so the UI
 * only shows actions a user can actually perform. The backend still
 * enforces everything (these are UX gates, not security), but without them
 * every account looked like an admin because all controls were visible.
 *
 * Roles:
 *  - ADMIN    — full access to everything
 *  - LEAD     — manages tasks/people within their department subtree
 *  - EMPLOYEE — works their own tasks: comment, change status/progress;
 *               cannot create top-level work, delete others' tasks, or
 *               manage the team
 */

type TaskLike = { created_by_id?: string; assignee_id?: string | null };

export function isAdmin(user: User | null | undefined): boolean {
  return user?.role === 'ADMIN';
}

export function isLead(user: User | null | undefined): boolean {
  return user?.role === 'LEAD';
}

export function isEmployee(user: User | null | undefined): boolean {
  return user?.role === 'EMPLOYEE';
}

/** Can create brand-new top-level tasks (the global "+" / "Создать"). */
export function canCreateTask(user: User | null | undefined): boolean {
  return user?.role === 'ADMIN' || user?.role === 'LEAD';
}

/** Can delete a task — admin, or the person who created it. */
export function canDeleteTask(user: User | null | undefined, task: TaskLike): boolean {
  if (!user) return false;
  if (user.role === 'ADMIN') return true;
  return task.created_by_id === user.id;
}

/**
 * Can edit a task's "meta" fields (title, description, assignee, dates,
 * priority). Employees may only touch status/progress on their own tasks —
 * everything else is read-only for them.
 */
export function canEditTaskMeta(user: User | null | undefined, task: TaskLike): boolean {
  if (!user) return false;
  if (user.role === 'ADMIN' || user.role === 'LEAD') return true;
  return task.created_by_id === user.id;
}

/** Can change status/progress — anyone who can see a task they own/lead. */
export function canUpdateProgress(user: User | null | undefined, task: TaskLike): boolean {
  if (!user) return false;
  if (user.role === 'ADMIN' || user.role === 'LEAD') return true;
  return task.assignee_id === user.id || task.created_by_id === user.id;
}

/** Can manage the team (create users, change roles). Admin only. */
export function canManageTeam(user: User | null | undefined): boolean {
  return user?.role === 'ADMIN';
}
