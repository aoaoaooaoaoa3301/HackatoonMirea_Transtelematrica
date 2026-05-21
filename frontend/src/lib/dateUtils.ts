import { format, formatDistanceToNow, parseISO, isValid } from 'date-fns';
import { ru } from 'date-fns/locale';

/**
 * Parse a timestamp coming from the backend.
 *
 * The backend stores naive UTC timestamps (created_at / updated_at / comment
 * times have no timezone suffix). `parseISO` interprets a tz-less datetime as
 * *local* time, which makes a just-created comment look like it was posted
 * "3 hours ago" in Moscow (UTC+3). To fix this we treat a tz-less datetime as
 * UTC by appending 'Z'. Date-only values ("2026-05-19") are left untouched —
 * they have no time component and no offset problem.
 */
export function parseServerDate(dateStr: string): Date {
  const hasTime = dateStr.includes('T');
  const hasTz = /([zZ])|([+-]\d{2}:?\d{2})$/.test(dateStr);
  if (hasTime && !hasTz) {
    return parseISO(dateStr + 'Z');
  }
  return parseISO(dateStr);
}

export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '—';
  const d = parseServerDate(dateStr);
  if (!isValid(d)) return '—';
  return format(d, 'd MMM yyyy', { locale: ru });
}

export function formatDateShort(dateStr: string | null | undefined): string {
  if (!dateStr) return '—';
  const d = parseServerDate(dateStr);
  if (!isValid(d)) return '—';
  return format(d, 'd MMM', { locale: ru });
}

export function formatRelative(dateStr: string | null | undefined): string {
  if (!dateStr) return '—';
  const d = parseServerDate(dateStr);
  if (!isValid(d)) return '—';
  return formatDistanceToNow(d, { addSuffix: true, locale: ru });
}

export function formatDateTime(dateStr: string | null | undefined): string {
  if (!dateStr) return '—';
  const d = parseServerDate(dateStr);
  if (!isValid(d)) return '—';
  return format(d, 'd MMM yyyy, HH:mm', { locale: ru });
}

export function toInputDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '';
  const d = parseServerDate(dateStr);
  if (!isValid(d)) return '';
  return format(d, 'yyyy-MM-dd');
}
