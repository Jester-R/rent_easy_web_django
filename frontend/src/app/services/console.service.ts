import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import {
  Booking,
  ConsoleBookingsResponse,
  ConsoleDashboardData,
  ConsolePaymentsResponse,
  ConsolePropertiesResponse,
  ConsoleUsersResponse,
  Payment,
  Property,
  Refund,
  User,
} from '../models';

@Injectable({
  providedIn: 'root',
})
export class ConsoleService {
  private readonly http = inject(HttpClient);
  private readonly base = '/console';

  private readonly opts = { withCredentials: true };

  /* ------------------------------- dashboard ------------------------------- */

  getDashboard(): Observable<ConsoleDashboardData> {
    return this.http.get<ConsoleDashboardData>(`${this.base}/`, this.opts);
  }

  /* --------------------------------- users --------------------------------- */

  getUsers(filters?: { q?: string; role?: string }): Observable<ConsoleUsersResponse> {
    let params = new HttpParams();
    if (filters?.q) params = params.set('q', filters.q);
    if (filters?.role && filters.role !== 'all') params = params.set('role', filters.role);
    return this.http.get<ConsoleUsersResponse>(`${this.base}/users/`, {
      params,
      withCredentials: true,
    });
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
  }): Observable<ConsolePropertiesResponse> {
    let params = new HttpParams();
    if (filters?.q) params = params.set('q', filters.q);
    if (filters?.owner) params = params.set('owner', filters.owner);
    return this.http.get<ConsolePropertiesResponse>(`${this.base}/properties/`, {
      params,
      withCredentials: true,
    });
  }

  createProperty(data: Record<string, unknown>): Observable<{ property: Property }> {
    return this.http.post<{ property: Property }>(
      `${this.base}/properties/new/`,
      data,
      this.opts
    );
  }

  updateProperty(id: number, data: Record<string, unknown>): Observable<{ property: Property }> {
    return this.http.post<{ property: Property }>(
      `${this.base}/properties/${id}/edit/`,
      data,
      this.opts
    );
  }

  deleteProperty(id: number): Observable<{ ok: boolean; deleted: number }> {
    return this.http.post<{ ok: boolean; deleted: number }>(
      `${this.base}/properties/${id}/delete/`,
      {},
      this.opts
    );
  }

  bulkDeleteProperties(ids: number[]): Observable<{ ok: boolean }> {
    return this.http.post<{ ok: boolean }>(
      `${this.base}/properties/bulk-delete/`,
      { ids },
      this.opts
    );
  }

  /* ------------------------------- bookings ------------------------------- */

  getBookings(filters?: { q?: string; status?: string }): Observable<ConsoleBookingsResponse> {
    let params = new HttpParams();
    if (filters?.q) params = params.set('q', filters.q);
    if (filters?.status && filters.status !== 'all') params = params.set('status', filters.status);
    return this.http.get<ConsoleBookingsResponse>(`${this.base}/bookings/`, {
      params,
      withCredentials: true,
    });
  }

  createBooking(data: Record<string, unknown>): Observable<{ booking: Booking }> {
    return this.http.post<{ booking: Booking }>(`${this.base}/bookings/new/`, data, this.opts);
  }

  updateBooking(id: number, data: Record<string, unknown>): Observable<{ booking: Booking }> {
    return this.http.post<{ booking: Booking }>(
      `${this.base}/bookings/${id}/edit/`,
      data,
      this.opts
    );
  }

  deleteBooking(id: number): Observable<{ ok: boolean; deleted: number }> {
    return this.http.post<{ ok: boolean; deleted: number }>(
      `${this.base}/bookings/${id}/delete/`,
      {},
      this.opts
    );
  }

  bulkDeleteBookings(ids: number[]): Observable<{ ok: boolean }> {
    return this.http.post<{ ok: boolean }>(
      `${this.base}/bookings/bulk-delete/`,
      { ids },
      this.opts
    );
  }

  /* -------------------------------- payments -------------------------------- */

  getPayments(filters?: { q?: string; status?: string }): Observable<ConsolePaymentsResponse> {
    let params = new HttpParams();
    if (filters?.q) params = params.set('q', filters.q);
    if (filters?.status && filters.status !== 'all') params = params.set('status', filters.status);
    return this.http.get<ConsolePaymentsResponse>(`${this.base}/payments/`, {
      params,
      withCredentials: true,
    });
  }

  createPayment(data: Record<string, unknown>): Observable<{ payment: Payment }> {
    return this.http.post<{ payment: Payment }>(
      `${this.base}/payments/new/`,
      data,
      this.opts
    );
  }

  updatePayment(id: number, data: Record<string, unknown>): Observable<{ payment: Payment }> {
    return this.http.post<{ payment: Payment }>(
      `${this.base}/payments/${id}/edit/`,
      data,
      this.opts
    );
  }

  deletePayment(id: number): Observable<{ ok: boolean; deleted: number }> {
    return this.http.post<{ ok: boolean; deleted: number }>(
      `${this.base}/payments/${id}/delete/`,
      {},
      this.opts
    );
  }

  bulkDeletePayments(ids: number[]): Observable<{ ok: boolean }> {
    return this.http.post<{ ok: boolean }>(
      `${this.base}/payments/bulk-delete/`,
      { ids },
      this.opts
    );
  }

  /* --------------------------------- refunds --------------------------------- */

  createRefund(data: { payment: number; reason?: string }): Observable<{ refund: Refund }> {
    return this.http.post<{ refund: Refund }>(`${this.base}/refunds/new/`, data, this.opts);
  }

  processRefund(id: number): Observable<{ ok: boolean; refund: Refund }> {
    return this.http.post<{ ok: boolean; refund: Refund }>(
      `${this.base}/refunds/${id}/process/`,
      {},
      this.opts
    );
  }
}
