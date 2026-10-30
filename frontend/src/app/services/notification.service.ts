import { Injectable, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, Subscription, tap } from 'rxjs';
import { AppNotification } from '../models';

@Injectable({
  providedIn: 'root',
})
export class NotificationService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = '/api';

  readonly unreadCount = signal<number>(0);
  readonly preview = signal<AppNotification[]>([]);
  /** Most recent notification pushed over SSE (null before the first one). */
  readonly incoming = signal<AppNotification | null>(null);

  private stream: EventSource | null = null;
  private refreshTimer: number | null = null;
  private refreshRequest: Subscription | null = null;

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

    // SSE can be buffered or terminated by an intermediary. Keep the bell
    // current with a small preview refresh as a fallback for those cases.
    this.refreshPreview();
    this.refreshTimer = window.setInterval(() => this.refreshPreview(), 3_000);

    stream.addEventListener('ready', (event: MessageEvent) => {
      try {
        const payload = JSON.parse(event.data) as { unread?: number };
        if (typeof payload.unread === 'number') {
          this.unreadCount.set(payload.unread);
        }
      } catch {
        // Ignore malformed keep-alive payloads.
      }
    });

    stream.addEventListener('notification', (event: MessageEvent) => {
      try {
        const item = JSON.parse(event.data) as AppNotification;
        this.unreadCount.update((count) => count + 1);
        this.incoming.set(item);
      } catch {
        // Ignore malformed events and wait for the next one.
      }
    });
  }

  disconnect(): void {
    this.stream?.close();
    this.stream = null;
    if (this.refreshTimer !== null) {
      window.clearInterval(this.refreshTimer);
      this.refreshTimer = null;
    }
    this.refreshRequest?.unsubscribe();
    this.refreshRequest = null;
  }

  private refreshPreview(): void {
    if (this.refreshRequest && !this.refreshRequest.closed) return;
    this.refreshRequest = this.getPreview().subscribe();
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

  getBadge(): Observable<{ unread: number }> {
    return this.http
      .get<{ unread: number }>(`${this.baseUrl}/notifications/badge/`, {
        withCredentials: true,
      })
      .pipe(
        tap((res) => {
          this.unreadCount.set(res.unread);
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

  toggleRead(id: number): Observable<{ ok: boolean; read: boolean }> {
    return this.http.post<{ ok: boolean; read: boolean }>(
      `${this.baseUrl}/notifications/${id}/toggle-read/`,
      {},
      { withCredentials: true }
    );
  }
}
