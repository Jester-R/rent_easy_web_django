import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { Booking, Payment } from '../models';

export interface BookingListResponse {
  bookings: Booking[];
  counts: Record<string, number>;
  status: string;
}

@Injectable({
  providedIn: 'root',
})
export class BookingService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = '';

  getRenterBookings(status: string = 'all'): Observable<BookingListResponse> {
    let params = new HttpParams();
    if (status) params = params.set('status', status);
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

  payBooking(
    id: number,
    data: { method?: string; simulate?: string }
  ): Observable<{ payment: Payment; already_paid: boolean }> {
    return this.http.post<{ payment: Payment; already_paid: boolean }>(
      `${this.baseUrl}/rent/bookings/${id}/pay/`,
      data,
      { withCredentials: true }
    );
  }

  getOwnerBookings(status: string = 'all'): Observable<BookingListResponse> {
    let params = new HttpParams();
    if (status) params = params.set('status', status);
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
}
