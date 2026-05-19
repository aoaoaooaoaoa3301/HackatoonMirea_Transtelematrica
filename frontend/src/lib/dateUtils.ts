import { format, formatDistanceToNow, parseISO, isValid } from 'date-fns';
import { ru } from 'date-fns/locale';

export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '—';
  const d = parseISO(dateStr);
  if (!isValid(d)) return '—';
  return format(d, 'd MMM yyyy', { locale: ru });
}

export function formatDateShort(dateStr: string | null | undefined): string {
  if (!dateStr) return '—';
  const d = parseISO(dateStr);
  if (!isValid(d)) return '—';
  return format(d, 'd MMM', { locale: ru });
}

export function formatRelative(dateStr: string | null | undefined): string {
  if (!dateStr) return '—';
  const d = parseISO(dateStr);
  if (!isValid(d)) return '—';
  return formatDistanceToNow(d, { addSuffix: true, locale: ru });
}

export function formatDateTime(dateStr: string | null | undefined): string {
  if (!dateStr) return '—';
  const d = parseISO(dateStr);
  if (!isValid(d)) return '—';
  return format(d, 'd MMM yyyy, HH:mm', { locale: ru });
}

export function toInputDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '';
  const d = parseISO(dateStr);
  if (!isValid(d)) return '';
  return format(d, 'yyyy-MM-dd');
}
