import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Router, RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { BookingService, BookingListResponse } from '../../../services/booking.service';
import { ChatService } from '../../../services/chat.service';
import { PaymentService } from '../../../services/payment.service';
import { Booking } from '../../../models';
import { IconComponent } from '../../../components/icon/icon';
import { DataPaginationComponent } from '../../../components/data-pagination/data-pagination';
import { SelectOption } from '../../../components/searchable-select/searchable-select';
import { LanguageService } from '../../../services/language.service';
import { propertyLocation, propertyTitle } from '../../../shared/property-text';
import type { Property } from '../../../models';
import type { PaymentMethodDetail } from '../../../models';
import { bookingPill, PAYMENT_METHOD_OPTIONS } from '../../../shared/ui';

@Component({
  selector: 'app-renter-bookings',
  imports: [CommonModule, RouterLink, FormsModule, IconComponent, DataPaginationComponent],
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
  private readonly chat = inject(ChatService);
  private readonly paymentService = inject(PaymentService);
  private readonly router = inject(Router);

  bookings = signal<Booking[]>([]);
  counts = signal<Record<string, number>>({});
  total = signal(0);
  page = signal(1);
  readonly pageSize = 25;
  activeTab = signal<string>('all');
  isLoading = signal(true);
  isOpeningChatId = signal<number | null>(null);
  isOpeningOwnerChatId = signal<number | null>(null);
  chatError = signal<string | null>(null);

  label(value: string): string {
    return this.language.valueLabel(value);
  }

  refundStatePill(state: string): string {
    if (state === 'Refunded') return 'pill-refunded';
    if (state === 'Refund failed') return 'pill-rejected';
    return 'pill-pending';
  }

  bookingState(b: Booking): { label: string; pill: string } {
    const status = this.label(b.status);
    if (b.refund_state) {
      return {
        label: this.label(b.refund_state),
        pill: this.refundStatePill(b.refund_state),
      };
    }
    if (b.is_paid && b.status !== 'Confirmed') {
      return {
        label: `${status} · ${this.language.t('renterBookings.paid')}`,
        pill: bookingPill(b.status),
      };
    }
    return { label: status, pill: bookingPill(b.status) };
  }

  openOwnerChat(b: Booking): void {
    if (this.isOpeningOwnerChatId() !== null) return;
    this.chatError.set(null);
    this.isOpeningOwnerChatId.set(b.id);
    this.chat.openBookingChat(b.id).subscribe({
      next: (res) => {
        this.isOpeningOwnerChatId.set(null);
        void this.router.navigateByUrl(`/messages/${res.conversation.id}`);
      },
      error: (err: HttpErrorResponse) => {
        this.isOpeningOwnerChatId.set(null);
        this.chatError.set(
          err.error?.detail || this.language.t('renterBookings.ownerChatUnavailable')
        );
      },
    });
  }

  canOpenRefundChat(b: Booking): boolean {
    return !!b.refund_id && ['Accepted', 'Processed'].includes(b.refund_status || '');
  }

  openRefundChat(b: Booking): void {
    if (!b.refund_id || !this.canOpenRefundChat(b) || this.isOpeningChatId() !== null) return;
    this.chatError.set(null);
    this.isOpeningChatId.set(b.id);
    this.chat.openRefundChat(b.refund_id).subscribe({
      next: (res) => {
        this.isOpeningChatId.set(null);
        void this.router.navigateByUrl(res.url);
      },
      error: (err: HttpErrorResponse) => {
        this.isOpeningChatId.set(null);
        this.chatError.set(
          err.error?.detail || this.language.t('renterBookings.refundChatUnavailable')
        );
      },
    });
  }

  // Pay modal state
  readonly methods = PAYMENT_METHOD_OPTIONS.map((m) => m.value);

  readonly methodOptions: SelectOption[] = [...PAYMENT_METHOD_OPTIONS];
  selectedBookingForPay = signal<Booking | null>(null);
  selectedPaymentMethod = PAYMENT_METHOD_OPTIONS[0].value;
  paymentMethodDetails = signal<Record<string, PaymentMethodDetail>>({});
  isPaying = signal(false);
  paySuccessMessage = signal<string | null>(null);
  payErrorMessage = signal<string | null>(null);
  payQr = signal<{ image: string; deeplink?: string; amount: number | string; currency: string } | null>(null);

  ngOnInit(): void {
    this.loadBookings();
    this.paymentService.getPaymentMethodDetails().subscribe({
      next: (res) => this.paymentMethodDetails.set(res.payment_method_details),
      error: () => undefined,
    });
  }

  selectedPaymentInfo(): PaymentMethodDetail | null {
    return this.paymentMethodDetails()[this.selectedPaymentMethod] || null;
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

  formatRemaining(hours: number | undefined | null): string {
    const value = Math.max(0, Number(hours) || 0);
    if (value <= 0) return this.language.t('renterBookings.lessThanHour');
    const totalMinutes = Math.floor(value * 60);
    const h = Math.floor(totalMinutes / 60);
    const m = totalMinutes % 60;
    if (h <= 0) return `${m}m`;
    if (m <= 0) return `${h}h`;
    return `${h}h ${m}m`;
  }

  changePage(page: number): void {
    this.page.set(page);
    this.loadBookings();
  }

  cancelBooking(booking: Booking): void {
    const message = booking.is_paid
      ? window.prompt(this.language.t('renterBookings.refundMessagePrompt'), '')
      : '';
    if (message === null) return;
    if (booking.is_paid && !message.trim()) {
      alert(this.language.t('renterBookings.refundMessageRequired'));
      return;
    }
    if (!booking.is_paid && !confirm('Are you sure you want to cancel this booking request?')) return;

    this.bookingService.cancelBooking(booking.id, message).subscribe({
      next: () => {
        this.loadBookings();
      },
    });
  }

  openPayModal(booking: Booking): void {
    this.selectedBookingForPay.set(booking);
    this.paySuccessMessage.set(null);
    this.payErrorMessage.set(null);
    this.payQr.set(null);
  }

  closePayModal(): void {
    if (this.isPaying()) return;
    this.selectedBookingForPay.set(null);
    this.payQr.set(null);
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
      })
      .subscribe({
        next: (res) => {
          if (res.qr) {
            this.payQr.set(res.qr);
            this.isPaying.set(false);
            return;
          }
          const checkout = res.checkout;
          if (checkout && 'url' in checkout && checkout.url) {
            // Stripe's hosted checkout must be opened as a full navigation.
            window.location.href = checkout.url;
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
          const detail = String(err.error?.detail || '');
          if (detail.startsWith('stripe_error')) {
            this.payErrorMessage.set(
              detail.includes('not_configured')
                ? 'Stripe is not configured. Add STRIPE_SECRET_KEY to the backend .env and restart.'
                : 'Stripe is unavailable. Please try again.'
            );
            return;
          }
          if (detail === 'unsupported_payment_method') {
            this.payErrorMessage.set('Choose a supported payment method.');
            return;
          }
          this.payErrorMessage.set(`Payment failed: ${detail || 'Unknown error'}`);
        },
      });
  }
}
