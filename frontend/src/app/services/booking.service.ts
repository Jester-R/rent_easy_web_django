import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { Booking, HostedCheckout, Payment } from '../models';

export interface PayBookingResponse {
  payment: Payment;
  already_paid: boolean;
  checkout?: HostedCheckout | null;
}

export interface BookingListResponse {
  bookings: Booking[];
  counts: Record<string, number>;
  status: string;
  total: number;
  page: number;
  page_size: number;
}

@Injectable({
  providedIn: 'root',
})
export class BookingService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = '/api';

  getRenterBookings(status: string = 'all', page = 1, pageSize = 25): Observable<BookingListResponse> {
    let params = new HttpParams();
    if (status) params = params.set('status', status);
    params = params.set('page', String(page)).set('page_size', String(pageSize));
    return this.http.get<BookingListResponse>(`${this.baseUrl}/rent/bookings/`, {
      params,
      withCredentials: true,
    });
  }

  getRenterBooking(id: number): Observable<{ booking: Booking; audience: string }> {
    return this.http.get<{ booking: Booking; audience: string }>(
      `${this.baseUrl}/rent/bookings/${id}/`,
      { withCredentials: true }
    );
  }

  cancelBooking(id: number): Observable<{ ok: boolean; booking: Booking }> {
    return this.http.post<{ ok: boolean; booking: Booking }>(
      `${this.baseUrl}/rent/bookings/${id}/cancel/`,
      {},
      { withCredentials: true }
    );
  }

  confirmBooking(id: number): Observable<{ ok: boolean; booking: Booking }> {
    return this.http.post<{ ok: boolean; booking: Booking }>(
      `${this.baseUrl}/rent/bookings/${id}/confirm/`,
      {},
      { withCredentials: true }
    );
  }

  payBooking(
    id: number,
    data: { method?: string; simulate?: string }
  ): Observable<PayBookingResponse> {
    return this.http.post<PayBookingResponse>(
      `${this.baseUrl}/rent/bookings/${id}/pay/`,
      data,
      { withCredentials: true }
    );
  }

  getOwnerBookings(status: string = 'all', page = 1, pageSize = 25): Observable<BookingListResponse> {
    let params = new HttpParams();
    if (status) params = params.set('status', status);
    params = params.set('page', String(page)).set('page_size', String(pageSize));
    return this.http.get<BookingListResponse>(`${this.baseUrl}/owner/bookings/`, {
      params,
      withCredentials: true,
    });
  }

  getOwnerBooking(id: number): Observable<{ booking: Booking; audience: string }> {
    return this.http.get<{ booking: Booking; audience: string }>(
      `${this.baseUrl}/owner/bookings/${id}/`,
      { withCredentials: true }
    );
  }

  approveBooking(id: number): Observable<{ ok: boolean; booking: Booking }> {
    return this.http.post<{ ok: boolean; booking: Booking }>(
      `${this.baseUrl}/owner/bookings/${id}/approve/`,
      {},
      { withCredentials: true }
    );
  }

  rejectBooking(id: number): Observable<{ ok: boolean; booking: Booking }> {
    return this.http.post<{ ok: boolean; booking: Booking }>(
      `${this.baseUrl}/owner/bookings/${id}/reject/`,
      {},
      { withCredentials: true }
    );
  }

  ownerCancelBooking(id: number): Observable<{ ok: boolean; booking: Booking }> {
    return this.http.post<{ ok: boolean; booking: Booking }>(
      `${this.baseUrl}/owner/bookings/${id}/cancel/`,
      {},
      { withCredentials: true }
    );
  }
}
