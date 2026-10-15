import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { BookingService, BookingListResponse } from '../../../services/booking.service';
import { Booking } from '../../../models';
import { IconComponent } from '../../../components/icon/icon';
import { DataPaginationComponent } from '../../../components/data-pagination/data-pagination';
import {
  SearchableSelectComponent,
  SelectOption,
} from '../../../components/searchable-select/searchable-select';
import { LanguageService } from '../../../services/language.service';
import { propertyLocation, propertyTitle } from '../../../shared/property-text';
import type { Property } from '../../../models';
import { PAYMENT_METHODS, submitHostedCheckout } from '../../../shared/ui';

@Component({
  selector: 'app-renter-bookings',
  imports: [CommonModule, RouterLink, FormsModule, IconComponent, SearchableSelectComponent, DataPaginationComponent],
  templateUrl: './renter-bookings.html',
})
export class RenterBookingsComponent implements OnInit {
  readonly language = inject(LanguageService);

  title(property: Property): string {
    return propertyTitle(property, this.language.current());
  }

  location(property: Property): string {
    return propertyLocation(property, this.language.current());
  }
  private readonly bookingService = inject(BookingService);

  bookings = signal<Booking[]>([]);
  counts = signal<Record<string, number>>({});
  total = signal(0);
  page = signal(1);
  readonly pageSize = 25;
  activeTab = signal<string>('all');
  isLoading = signal(true);

  label(value: string): string {
    return this.language.valueLabel(value);
  }

  // Pay modal state
  readonly methods = PAYMENT_METHODS;

  readonly methodOptions: SelectOption[] = PAYMENT_METHODS.map((m) => ({ value: m, label: m }));
  selectedBookingForPay = signal<Booking | null>(null);
  selectedPaymentMethod = PAYMENT_METHODS[0];
  isPaying = signal(false);
  paySuccessMessage = signal<string | null>(null);
  payErrorMessage = signal<string | null>(null);

  ngOnInit(): void {
    this.loadBookings();
  }

  loadBookings(status: string = this.activeTab()): void {
    this.isLoading.set(true);
    if (status !== this.activeTab()) this.page.set(1);
    this.activeTab.set(status);
    this.bookingService.getRenterBookings(status, this.page(), this.pageSize).subscribe({
      next: (res: BookingListResponse) => {
        this.bookings.set(res.bookings);
        this.counts.set(res.counts);
        this.total.set(res.total);
        this.page.set(res.page);
        this.isLoading.set(false);
      },
      error: () => this.isLoading.set(false),
    });
  }

  changePage(page: number): void {
    this.page.set(page);
    this.loadBookings();
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
        simulate: this.selectedPaymentMethod.includes('(Mock)') ? 'success' : undefined,
      })
      .subscribe({
        next: (res) => {
          if (res.checkout) {
            this.paySuccessMessage.set('Redirecting to ABA PayWay…');
            submitHostedCheckout(res.checkout);
            return;
          }
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
