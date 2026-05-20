import apiClient from './client';

export interface TelegramStatus {
  connected: boolean;
  telegram_user_id?: number;
  telegram_username?: string | null;
  linked_at?: string | null;
}

export interface TelegramLinkCode {
  code: string;
  expires_at: string;
  instruction: string;
}

export async function getTelegramStatus(): Promise<TelegramStatus> {
  const { data } = await apiClient.get<TelegramStatus>('/telegram/status');
  return data;
}

export async function startTelegramLink(): Promise<TelegramLinkCode> {
  const { data } = await apiClient.post<TelegramLinkCode>('/telegram/link/start');
  return data;
}
