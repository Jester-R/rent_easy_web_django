import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { Payment, Payout, PayoutAccount, PayoutTotals, Refund } from '../models';

export interface RenterPaymentsResponse {
  payments: Payment[];
  query: string;
  total: number;
  page: number;
  page_size: number;
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
  payouts: Payout[];
  payout_totals: PayoutTotals;
  payout_account: PayoutAccount;
  total: number;
  refunds_total: number;
  refund_page: number;
  refund_page_size: number;
  payouts_total: number;
  payout_page: number;
  payout_page_size: number;
  page: number;
  page_size: number;
}

@Injectable({
  providedIn: 'root',
})
export class PaymentService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = '/api';

  getRenterPayments(filters?: {
    q?: string;
    status?: string;
    method?: string;
    page?: number;
    page_size?: number;
  }): Observable<RenterPaymentsResponse> {
    let params = new HttpParams();
    if (filters?.q) params = params.set('q', filters.q);
    if (filters?.status) params = params.set('status', filters.status);
    if (filters?.method) params = params.set('method', filters.method);
    if (filters?.page) params = params.set('page', String(filters.page));
    if (filters?.page_size) params = params.set('page_size', String(filters.page_size));

    return this.http.get<RenterPaymentsResponse>(`${this.baseUrl}/rent/payments/`, {
      params,
      withCredentials: true,
    });
  }

  getRenterPayment(id: number): Observable<{ payment: Payment; refund?: Refund | null; audience: string }> {
    return this.http.get<{ payment: Payment; refund?: Refund | null; audience: string }>(
      `${this.baseUrl}/rent/payments/${id}/`,
      { withCredentials: true }
    );
  }

  refreshRenterPayment(id: number): Observable<{ payment: Payment }> {
    return this.http.post<{ payment: Payment }>(
      `${this.baseUrl}/rent/payments/${id}/refresh/`,
      {},
      { withCredentials: true }
    );
  }

  getOwnerPayments(filters?: {
    q?: string;
    status?: string;
    refund?: string;
    method?: string;
    page?: number;
    page_size?: number;
    payout_page?: number;
    payout_page_size?: number;
    refund_page?: number;
    refund_page_size?: number;
  }): Observable<OwnerPaymentsResponse> {
    let params = new HttpParams();
    if (filters?.q) params = params.set('q', filters.q);
    if (filters?.status) params = params.set('status', filters.status);
    if (filters?.refund) params = params.set('refund', filters.refund);
    if (filters?.method) params = params.set('method', filters.method);
    if (filters?.page) params = params.set('page', String(filters.page));
    if (filters?.page_size) params = params.set('page_size', String(filters.page_size));
    if (filters?.payout_page) params = params.set('payout_page', String(filters.payout_page));
    if (filters?.payout_page_size) params = params.set('payout_page_size', String(filters.payout_page_size));
    if (filters?.refund_page) params = params.set('refund_page', String(filters.refund_page));
    if (filters?.refund_page_size) params = params.set('refund_page_size', String(filters.refund_page_size));

    return this.http.get<OwnerPaymentsResponse>(`${this.baseUrl}/owner/payments/`, {
      params,
      withCredentials: true,
    });
  }

  getOwnerPayment(id: number): Observable<{ payment: Payment; refund?: Refund | null; audience: string }> {
    return this.http.get<{ payment: Payment; refund?: Refund | null; audience: string }>(
      `${this.baseUrl}/owner/payments/${id}/`,
      { withCredentials: true }
    );
  }

  requestRefund(id: number, request: { reason: string; request_note: string }): Observable<{ refund: Refund }> {
    return this.http.post<{ refund: Refund }>(
      `${this.baseUrl}/payments/${id}/refund/request/`,
      request,
      { withCredentials: true },
    );
  }

  refreshOwnerPayment(id: number): Observable<{ payment: Payment }> {
    return this.http.post<{ payment: Payment }>(
      `${this.baseUrl}/owner/payments/${id}/refresh/`,
      {},
      { withCredentials: true }
    );
  }

  processRefund(
    refundId: number,
    options?: { external?: boolean; note?: string }
  ): Observable<{ ok: boolean; refund: Refund }> {
    return this.http.post<{ ok: boolean; refund: Refund }>(
      `${this.baseUrl}/owner/payments/refunds/${refundId}/process/`,
      options ?? {},
      { withCredentials: true }
    );
  }
}
