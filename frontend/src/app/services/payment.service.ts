import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { Payment, Refund } from '../models';

export interface RenterPaymentsResponse {
  payments: Payment[];
  query: string;
}

export interface OwnerPaymentsResponse {
  payments: Payment[];
  pending_refunds: Refund[];
  renter_count: number;
  totals: {
    revenue: number;
    refunded: number;
    count: number;
  };
}

@Injectable({
  providedIn: 'root',
})
export class PaymentService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = '';

  getRenterPayments(filters?: {
    q?: string;
    status?: string;
    method?: string;
  }): Observable<RenterPaymentsResponse> {
    let params = new HttpParams();
    if (filters?.q) params = params.set('q', filters.q);
    if (filters?.status) params = params.set('status', filters.status);
    if (filters?.method) params = params.set('method', filters.method);

    return this.http.get<RenterPaymentsResponse>(`${this.baseUrl}/rent/payments/`, {
      params,
      withCredentials: true,
    });
  }

  getRenterPayment(id: number): Observable<{ payment: Payment; audience: string }> {
    return this.http.get<{ payment: Payment; audience: string }>(
      `${this.baseUrl}/rent/payments/${id}/`,
      { withCredentials: true }
    );
  }

  getOwnerPayments(filters?: {
    status?: string;
    refund?: string;
    method?: string;
  }): Observable<OwnerPaymentsResponse> {
    let params = new HttpParams();
    if (filters?.status) params = params.set('status', filters.status);
    if (filters?.refund) params = params.set('refund', filters.refund);
    if (filters?.method) params = params.set('method', filters.method);

    return this.http.get<OwnerPaymentsResponse>(`${this.baseUrl}/owner/payments/`, {
      params,
      withCredentials: true,
    });
  }

  getOwnerPayment(id: number): Observable<{ payment: Payment; audience: string }> {
    return this.http.get<{ payment: Payment; audience: string }>(
      `${this.baseUrl}/owner/payments/${id}/`,
      { withCredentials: true }
    );
  }

  processRefund(refundId: number): Observable<{ ok: boolean; refund: Refund }> {
    return this.http.post<{ ok: boolean; refund: Refund }>(
      `${this.baseUrl}/owner/payments/refunds/${refundId}/process/`,
      {},
      { withCredentials: true }
    );
  }
}
