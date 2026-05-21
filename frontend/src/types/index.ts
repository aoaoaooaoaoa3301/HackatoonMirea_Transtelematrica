export type Role = 'EMPLOYEE' | 'LEAD' | 'ADMIN';
export type TaskType = 'GOAL' | 'EPIC' | 'TASK' | 'SUBTASK';
export type Priority = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
export type Status = 'NEW' | 'IN_PROGRESS' | 'REVIEW' | 'DONE' | 'OVERDUE';
export type PeriodBucket = 'year' | 'quarter' | 'month' | 'week';

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: Role;
  department_id: string | null;
  skills: string[];
  seniority: string | null;
  capacity_hours_per_week: number;
}

export interface Department {
  id: string;
  name: string;
  parent_id: string | null;
  head_user_id: string | null;
}

export interface Task {
  id: string;
  type: TaskType;
  title: string;
  description: string;
  parent_id: string | null;
  start_date: string | null;
  due_date: string | null;
  period_bucket: PeriodBucket;
  priority: Priority;
  status: Status;
  progress: number;
  assigned_department_id: string | null;
  assigned_department_name?: string | null;
  assignee_id: string | null;
  assignee_name?: string | null;
  created_by_id: string;
  created_by_name?: string | null;
  children_count?: number;
  created_at: string;
  updated_at: string;
  assignee?: User;
  department?: Department;
  children?: Task[];
}

export interface TaskComment {
  id: string;
  task_id: string;
  author_id: string;
  body: string;
  created_at: string;
  author?: User;
}

export interface TaskHistoryEvent {
  id: string;
  task_id: string;
  actor_id: string | null;
  event_type: string;
  payload: Record<string, unknown>;
  at: string;
}

export interface TaskDetail extends Task {
  children: Task[];
  parent_chain: Task[];
  comments: TaskComment[];
  history: TaskHistoryEvent[];
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface UserWorkload {
  open_tasks: number;
  weighted_load: number;
  overdue_count: number;
  at_risk_count: number;
  capacity_util: number;
}

export interface AnalyticsOverview {
  total_tasks: number;
  in_progress: number;
  overdue: number;
  at_risk: number;
  done: number;
  new_tasks: number;
  review: number;
  by_department: {
    department_id: string;
    department_name: string;
    total: number;
    done: number;
    in_progress: number;
    overdue: number;
  }[];
  by_status: {
    status: Status;
    count: number;
  }[];
  by_priority: {
    priority: Priority;
    count: number;
  }[];
}

export interface WorkloadEntry {
  user_id: string;
  full_name: string;
  department: string;
  open_tasks: number;
  weighted_load: number;
  overdue: number;
  at_risk: number;
  capacity_util: number;
}

export interface CompletionEntry {
  bucket_key: string;
  total: number;
  done: number;
  completion_pct: number;
}

export interface DelegationFlow {
  nodes: { id: string; name: string }[];
  links: { source: string; target: string; value: number }[];
}

export interface AIDigest {
  summary: string;
  key_points: string[];
}

export interface AIRisk {
  task_id: string;
  task_title: string;
  risk_level: 'high' | 'medium';
  reason: string;
}

export interface AIRisksResponse {
  items: AIRisk[];
}

export interface AIOverloadEntry {
  user_id: string;
  full_name: string;
  department: string;
  capacity_util: number;
  open_tasks: number;
  reason: string;
}

export interface AIParsedTask {
  title: string;
  description?: string;
  due_date?: string;
  priority: Priority;
  type: TaskType;
  assignee_suggestion?: string;
}

export interface AIAssigneeCandidate {
  user_id: string;
  full_name: string;
  score: number;
  reason: string;
}

export interface AIChatMessage {
  role: 'user' | 'assistant';
  content: string;
  buttons?: Array<{ label: string; callback_data: string }>;
}

export interface AIGoalSummary {
  progress: number;
  risks: string[];
  summary: string;
}

export interface TaskFilters {
  type?: TaskType[];
  status?: Status[];
  priority?: Priority[];
  department_id?: string;
  assignee_id?: string;
  q?: string;
  due_before?: string;
  due_after?: string;
  parent_id?: string;
  period_bucket?: PeriodBucket;
}

export interface CreateTaskPayload {
  type: TaskType;
  title: string;
  description?: string;
  parent_id?: string | null;
  start_date?: string | null;
  due_date?: string | null;
  period_bucket?: PeriodBucket;
  priority: Priority;
  status?: Status;
  assigned_department_id?: string | null;
  assignee_id?: string | null;
}

export interface UpdateTaskPayload {
  title?: string;
  description?: string;
  status?: Status;
  priority?: Priority;
  due_date?: string | null;
  start_date?: string | null;
  assignee_id?: string | null;
  assigned_department_id?: string | null;
  progress?: number;
  period_bucket?: PeriodBucket;
}
