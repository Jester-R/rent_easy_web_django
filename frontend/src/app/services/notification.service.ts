import { Injectable, PLATFORM_ID, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { isPlatformBrowser } from '@angular/common';
import { Observable, Subscription, tap } from 'rxjs';
import { AppNotification } from '../models';

@Injectable({
  providedIn: 'root',
})
export class NotificationService {
  private readonly http = inject(HttpClient);
  private readonly platformId = inject(PLATFORM_ID);
  private readonly baseUrl = '/api';

  readonly unreadCount = signal<number>(0);
  readonly preview = signal<AppNotification[]>([]);
  /** Most recent notification pushed over SSE (null before the first one). */
  readonly incoming = signal<AppNotification | null>(null);

  private stream: EventSource | null = null;
  private refreshRequest: Subscription | null = null;
  private lastPreviewRefresh = 0;

  /**
   * Open the Server-Sent Events notification stream. Safe to call repeatedly;
   * the browser reconnects on its own when the connection drops.
   */
  connect(): void {
    if (typeof window === 'undefined' || typeof EventSource === 'undefined') return;
    if (this.stream) return;

    const stream = new EventSource(`${this.baseUrl}/notifications/stream/`, {
      withCredentials: true,
    });
    this.stream = stream;

    stream.addEventListener('ready', (event: MessageEvent) => {
      try {
        const payload = JSON.parse(event.data) as { unread?: number };
        if (typeof payload.unread === 'number') {
          this.unreadCount.set(payload.unread);
        }
      } catch {
        // Ignore malformed keep-alive payloads.
      }
      this.refreshPreview();
    });

    stream.addEventListener('notification', (event: MessageEvent) => {
      try {
        const item = JSON.parse(event.data) as AppNotification;
        this.unreadCount.update((count) => count + 1);
        this.incoming.set(item);
      } catch {
        // Ignore malformed events and wait for the next one.
      }
      this.refreshPreview();
    });
  }

  disconnect(): void {
    this.stream?.close();
    this.stream = null;
    this.refreshRequest?.unsubscribe();
    this.refreshRequest = null;
    this.lastPreviewRefresh = 0;
  }

  refreshPreview(): void {
    if (!isPlatformBrowser(this.platformId) || document.hidden) return;
    const now = Date.now();
    if (now - this.lastPreviewRefresh < 1000) return;
    this.lastPreviewRefresh = now;
    this.refreshRequest?.unsubscribe();
    this.refreshRequest = this.getPreview().subscribe({
      error: () => undefined,
    });
  }

  getNotifications(page = 1, pageSize = 25): Observable<{ notifications: AppNotification[]; unread: number; total: number; page: number; page_size: number }> {
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    return this.http
      .get<{ notifications: AppNotification[]; unread: number; total: number; page: number; page_size: number }>(
        `${this.baseUrl}/notifications/?${params.toString()}`,
        { withCredentials: true }
      )
      .pipe(
        tap((res) => {
          this.unreadCount.set(res.unread);
        })
      );
  }

  getPreview(): Observable<{ items: AppNotification[]; unread: number }> {
    return this.http
      .get<{ items: AppNotification[]; unread: number }>(
        `${this.baseUrl}/notifications/preview/`,
        { withCredentials: true }
      )
      .pipe(
        tap((res) => {
          this.unreadCount.set(res.unread);
          this.preview.set(res.items || []);
        })
      );
  }

  readAll(): Observable<{ ok: boolean; unread: number }> {
    return this.http
      .post<{ ok: boolean; unread: number }>(
        `${this.baseUrl}/notifications/read-all/`,
        {},
        { withCredentials: true }
      )
      .pipe(
        tap(() => {
          this.unreadCount.set(0);
        })
      );
  }

  clearAll(): Observable<{ ok: boolean; deleted: number; unread: number }> {
    return this.http
      .post<{ ok: boolean; deleted: number; unread: number }>(
        `${this.baseUrl}/notifications/clear-all/`,
        {},
        { withCredentials: true }
      )
      .pipe(
        tap(() => {
          this.unreadCount.set(0);
          this.preview.set([]);
        })
      );
  }

  clear(id: number): Observable<{ ok: boolean }> {
    return this.http
      .post<{ ok: boolean }>(
        `${this.baseUrl}/notifications/${id}/clear/`,
        {},
        { withCredentials: true }
      )
      .pipe(
        tap(() => {
          this.preview.update((items) => items.filter((item) => item.id !== id));
        })
      );
  }

  toggleRead(id: number): Observable<{ ok: boolean; read: boolean; unread: number }> {
    return this.http.post<{ ok: boolean; read: boolean; unread: number }>(
      `${this.baseUrl}/notifications/${id}/toggle-read/`,
      {},
      { withCredentials: true }
    ).pipe(
      tap((res) => {
        this.unreadCount.set(res.unread);
        this.preview.update((items) =>
          items.map((item) => (item.id === id ? { ...item, read: res.read } : item))
        );
      })
    );
  }
}
