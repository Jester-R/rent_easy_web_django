import { Injectable, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap } from 'rxjs';
import { AppNotification } from '../models';

@Injectable({
  providedIn: 'root',
})
export class NotificationService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = '';

  readonly unreadCount = signal<number>(0);

  getNotifications(): Observable<{ notifications: AppNotification[]; unread: number }> {
    return this.http
      .get<{ notifications: AppNotification[]; unread: number }>(
        `${this.baseUrl}/notifications/`,
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
