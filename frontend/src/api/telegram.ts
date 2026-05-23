import apiClient from './client';

export interface TelegramStatus {
  connected: boolean;
  telegram_user_id?: number;
  telegram_username?: string | null;
  linked_at?: string | null;
  bot_username?: string | null;
}

export interface TelegramLinkCode {
  code: string;
  expires_at: string;
  instruction: string;
  deep_link?: string | null;
  bot_username?: string | null;
}

export async function getTelegramStatus(): Promise<TelegramStatus> {
  const { data } = await apiClient.get<TelegramStatus>('/telegram/status');
  return data;
}

export async function startTelegramLink(): Promise<TelegramLinkCode> {
  const { data } = await apiClient.post<TelegramLinkCode>('/telegram/link/start');
  return data;
}
