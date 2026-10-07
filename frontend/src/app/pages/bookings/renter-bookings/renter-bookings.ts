import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { BookingService, BookingListResponse } from '../../../services/booking.service';
import { Booking } from '../../../models';
import { IconComponent } from '../../../components/icon/icon';

@Component({
  selector: 'app-renter-bookings',
  imports: [CommonModule, RouterLink, FormsModule, IconComponent],
  templateUrl: './renter-bookings.html',
})
export class RenterBookingsComponent implements OnInit {
  private readonly bookingService = inject(BookingService);

  bookings = signal<Booking[]>([]);
  counts = signal<Record<string, number>>({});
  activeTab = signal<string>('all');
  isLoading = signal(true);

  // Pay modal state
  selectedBookingForPay = signal<Booking | null>(null);
  selectedPaymentMethod = 'ABA';
  simulateOutcome = 'success';
  isPaying = signal(false);
  paySuccessMessage = signal<string | null>(null);
  payErrorMessage = signal<string | null>(null);

  ngOnInit(): void {
    this.loadBookings();
  }

  loadBookings(status: string = this.activeTab()): void {
    this.isLoading.set(true);
    this.activeTab.set(status);
    this.bookingService.getRenterBookings(status).subscribe({
      next: (res: BookingListResponse) => {
        this.bookings.set(res.bookings);
        this.counts.set(res.counts);
        this.isLoading.set(false);
      },
      error: () => this.isLoading.set(false),
    });
  }

  cancelBooking(id: number): void {
    if (!confirm('Are you sure you want to cancel this booking request?')) return;

    this.bookingService.cancelBooking(id).subscribe({
      next: () => {
        this.loadBookings();
      },
    });
  }

  openPayModal(booking: Booking): void {
    this.selectedBookingForPay.set(booking);
    this.paySuccessMessage.set(null);
    this.payErrorMessage.set(null);
  }

  closePayModal(): void {
    this.selectedBookingForPay.set(null);
  }

  submitPayment(): void {
    const b = this.selectedBookingForPay();
    if (!b) return;

    this.isPaying.set(true);
    this.payErrorMessage.set(null);
    this.paySuccessMessage.set(null);

    this.bookingService
      .payBooking(b.id, {
        method: this.selectedPaymentMethod,
        simulate: this.simulateOutcome,
      })
      .subscribe({
        next: (res) => {
          this.isPaying.set(false);
          this.paySuccessMessage.set(`Payment processed successfully! Ref: ${res.payment.reference}`);
          setTimeout(() => {
            this.closePayModal();
            this.loadBookings();
          }, 1500);
        },
        error: (err) => {
          this.isPaying.set(false);
          const detail = err.error?.detail || '';
          this.payErrorMessage.set(`Payment failed: ${detail || 'Unknown error'}`);
        },
      });
  }
}
