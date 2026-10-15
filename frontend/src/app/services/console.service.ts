import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import {
  Booking,
  ConsoleBookingsResponse,
  ConsoleDashboardData,
  ConsolePaymentsResponse,
  ConsolePropertiesResponse,
  ConsoleSettings,
  ConsoleUsersResponse,
  Payment,
  Payout,
  Refund,
  User,
} from '../models';

@Injectable({
  providedIn: 'root',
})
export class ConsoleService {
  private readonly http = inject(HttpClient);
  private readonly base = '/api/console';

  private readonly opts = { withCredentials: true };

  /* ------------------------------- dashboard ------------------------------- */

  getDashboard(): Observable<ConsoleDashboardData> {
    return this.http.get<ConsoleDashboardData>(`${this.base}/`, this.opts);
  }

  /* ------------------------------- settings -------------------------------- */

  getSettings(): Observable<{ settings: ConsoleSettings }> {
    return this.http.get<{ settings: ConsoleSettings }>(`${this.base}/settings/`, this.opts);
  }

  updateSettings(settings: Partial<ConsoleSettings>): Observable<{ settings: ConsoleSettings }> {
    return this.http.post<{ settings: ConsoleSettings }>(
      `${this.base}/settings/`,
      settings,
      this.opts
    );
  }

  sendNotificationBroadcast(data: {
    target: 'owners' | 'renters' | 'all';
    title_en: string;
    title_km: string;
    body_en: string;
    body_km: string;
  }): Observable<{ ok: boolean; sent: number }> {
    return this.http.post<{ ok: boolean; sent: number }>(
      `${this.base}/notifications/broadcast/`,
      data,
      this.opts,
    );
  }

  /* --------------------------------- users --------------------------------- */

  getUsers(filters?: { q?: string; role?: string; approval?: string; page?: number; page_size?: number }): Observable<ConsoleUsersResponse> {
    let params = new HttpParams();
    if (filters?.q) params = params.set('q', filters.q);
    if (filters?.role && filters.role !== 'all') params = params.set('role', filters.role);
    if (filters?.approval && filters.approval !== 'all') params = params.set('approval', filters.approval);
    if (filters?.page) params = params.set('page', String(filters.page));
    if (filters?.page_size) params = params.set('page_size', String(filters.page_size));
    return this.http.get<ConsoleUsersResponse>(`${this.base}/users/`, {
      params,
      withCredentials: true,
    });
  }

  approveUser(id: number): Observable<{ user: User }> {
    return this.http.post<{ user: User }>(`${this.base}/users/${id}/approve/`, {}, this.opts);
  }

  rejectUser(id: number): Observable<{ user: User }> {
    return this.http.post<{ user: User }>(`${this.base}/users/${id}/reject/`, {}, this.opts);
  }

  getUser(id: number): Observable<{ user: User }> {
    return this.http.get<{ user: User }>(`${this.base}/users/${id}/`, this.opts);
  }

  createUser(data: Record<string, unknown>): Observable<{ user: User }> {
    return this.http.post<{ user: User }>(`${this.base}/users/new/`, data, this.opts);
  }

  updateUser(id: number, data: Record<string, unknown>): Observable<{ user: User }> {
    return this.http.post<{ user: User }>(`${this.base}/users/${id}/edit/`, data, this.opts);
  }

  deleteUser(id: number): Observable<{ ok: boolean; deleted: number }> {
    return this.http.post<{ ok: boolean; deleted: number }>(
      `${this.base}/users/${id}/delete/`,
      {},
      this.opts
    );
  }

  bulkDeleteUsers(ids: number[]): Observable<{ ok: boolean; deleted?: number }> {
    return this.http.post<{ ok: boolean; deleted?: number }>(
      `${this.base}/users/bulk-delete/`,
      { ids },
      this.opts
    );
  }

  /* ------------------------------ properties ------------------------------ */

  getProperties(filters?: {
    q?: string;
    owner?: string;
    page?: number;
    page_size?: number;
  }): Observable<ConsolePropertiesResponse> {
    let params = new HttpParams();
    if (filters?.q) params = params.set('q', filters.q);
    if (filters?.owner) params = params.set('owner', filters.owner);
    if (filters?.page) params = params.set('page', String(filters.page));
    if (filters?.page_size) params = params.set('page_size', String(filters.page_size));
    return this.http.get<ConsolePropertiesResponse>(`${this.base}/properties/`, {
      params,
      withCredentials: true,
    });
  }

  softDeleteProperty(id: number): Observable<{ ok: boolean; deleted: number; is_active: boolean }> {
    return this.http.post<{ ok: boolean; deleted: number; is_active: boolean }>(
      `${this.base}/properties/${id}/delete/`,
      {},
      this.opts
    );
  }

  /* ------------------------------- bookings ------------------------------- */

  getBookings(filters?: { q?: string; status?: string; page?: number; page_size?: number }): Observable<ConsoleBookingsResponse> {
    let params = new HttpParams();
    if (filters?.q) params = params.set('q', filters.q);
    if (filters?.status && filters.status !== 'all') params = params.set('status', filters.status);
    if (filters?.page) params = params.set('page', String(filters.page));
    if (filters?.page_size) params = params.set('page_size', String(filters.page_size));
    return this.http.get<ConsoleBookingsResponse>(`${this.base}/bookings/`, {
      params,
      withCredentials: true,
    });
  }

  /* -------------------------------- payments -------------------------------- */

  getPayments(filters?: { q?: string; status?: string; refund_status?: string; page?: number; page_size?: number; payout_page?: number; payout_page_size?: number; refund_page?: number; refund_page_size?: number }): Observable<ConsolePaymentsResponse> {
    let params = new HttpParams();
    if (filters?.q) params = params.set('q', filters.q);
    if (filters?.status && filters.status !== 'all') params = params.set('status', filters.status);
    if (filters?.refund_status && filters.refund_status !== 'all') params = params.set('refund_status', filters.refund_status);
    if (filters?.page) params = params.set('page', String(filters.page));
    if (filters?.page_size) params = params.set('page_size', String(filters.page_size));
    if (filters?.payout_page) params = params.set('payout_page', String(filters.payout_page));
    if (filters?.payout_page_size) params = params.set('payout_page_size', String(filters.payout_page_size));
    if (filters?.refund_page) params = params.set('refund_page', String(filters.refund_page));
    if (filters?.refund_page_size) params = params.set('refund_page_size', String(filters.refund_page_size));
    return this.http.get<ConsolePaymentsResponse>(`${this.base}/payments/`, {
      params,
      withCredentials: true,
    });
  }

  payPayout(id: number, note: string): Observable<{ ok: boolean; payout: Payout }> {
    return this.http.post<{ ok: boolean; payout: Payout }>(
      `${this.base}/payouts/${id}/pay/`,
      { note },
      this.opts
    );
  }

  /* --------------------------------- refunds --------------------------------- */

  createRefund(data: { payment: number; reason?: string }): Observable<{ refund: Refund }> {
    return this.http.post<{ refund: Refund }>(`${this.base}/refunds/new/`, data, this.opts);
  }

  processRefund(
    id: number,
    options?: { external?: boolean; note?: string }
  ): Observable<{ ok: boolean; refund: Refund }> {
    return this.http.post<{ ok: boolean; refund: Refund }>(
      `${this.base}/refunds/${id}/process/`,
      options ?? {},
      this.opts
    );
  }

  rejectRefund(id: number, note: string): Observable<{ ok: boolean; refund: Refund }> {
    return this.http.post<{ ok: boolean; refund: Refund }>(
      `${this.base}/refunds/${id}/reject/`,
      { note },
      this.opts
    );
  }
}
