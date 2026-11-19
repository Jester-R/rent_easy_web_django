import { Component, OnInit, computed, inject, input, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { HttpErrorResponse } from '@angular/common/http';
import { IconComponent } from '../../../components/icon/icon';
import {
  SearchableSelectComponent,
  SelectOption,
} from '../../../components/searchable-select/searchable-select';
import { AuthService } from '../../../services/auth.service';
import { BookingService } from '../../../services/booking.service';
import { ChatService } from '../../../services/chat.service';
import { PaymentService } from '../../../services/payment.service';
import { PropertyCategoryService } from '../../../services/property-category.service';
import { LanguageService } from '../../../services/language.service';
import {
  propertyDescription,
  propertyLocation,
  propertyTitle,
} from '../../../shared/property-text';
import type { Property } from '../../../models';
import { Booking, UserBrief } from '../../../models';
import type { PaymentMethodDetail } from '../../../models';
import {
  PAYMENT_METHOD_OPTIONS,
  bookingPill,
  initials,
  prettyDate,
  roleLabel,
  shortDate,
  usd,
} from '../../../shared/ui';

type Party = UserBrief & { avatar_hue?: number };
type BookingExt = Booking & { can_cancel?: boolean; can_owner_cancel?: boolean };

@Component({
  selector: 'app-booking-detail',
  imports: [RouterLink, FormsModule, IconComponent, SearchableSelectComponent],
  templateUrl: './booking-detail.html',
})
export class BookingDetailComponent implements OnInit {
  readonly language = inject(LanguageService);

  title(property: Property | null | undefined): string {
    return propertyTitle(property, this.language.current());
  }

  location(property: Property | null | undefined): string {
    return propertyLocation(property, this.language.current());
  }

  description(property: Property | null | undefined): string {
    return propertyDescription(property, this.language.current());
  }

  categoryLabel(value: string | null | undefined): string {
    return this.categories.label(value, this.language.current());
  }

  readonly id = input<string>();

  private readonly bookingService = inject(BookingService);
  private readonly chat = inject(ChatService);
  private readonly paymentService = inject(PaymentService);
  private readonly categories = inject(PropertyCategoryService);
  private readonly router = inject(Router);
  readonly auth = inject(AuthService);

  readonly booking = signal<BookingExt | null>(null);
  readonly loadError = signal<string | null>(null);
  readonly audience = signal<'renter' | 'owner'>('renter');
  readonly isLoading = signal(true);
  readonly isBusy = signal(false);
  readonly actionError = signal<string | null>(null);
  readonly activePropertyImage = signal(0);
  readonly propertyImageCount = computed(
    () => this.booking()?.property.images?.length ?? 0
  );
  readonly visiblePropertyImageIndexes = computed<number[]>(() => {
    const total = this.propertyImageCount();
    if (!total) return [];
    const active = Math.min(this.activePropertyImage(), total - 1);
    const limit = 5;
    if (total <= limit) return Array.from({ length: total }, (_, i) => i);
    const start = Math.min(Math.max(0, active - 2), total - limit);
    return Array.from({ length: limit }, (_, i) => start + i);
  });

  readonly statusBadge = computed(() => {
    const booking = this.booking();
    if (!booking) return { label: '', pill: 'pill-neutral' };
    const status = this.language.valueLabel(booking.status);
    if (booking.refund_state) {
      return {
        label: this.language.valueLabel(booking.refund_state),
        pill:
          booking.refund_state === 'Refunded'
            ? 'pill-refunded'
            : booking.refund_state === 'Refund failed'
              ? 'pill-rejected'
              : 'pill-pending',
      };
    }
    const payment = this.language.t(
      booking.is_paid ? 'bookingDetail.paid' : 'bookingDetail.unpaid'
    );
    const label = ['Pending', 'Approved', 'Confirmed'].includes(booking.status)
      ? `${status} ${payment}`
      : status;
    return { label, pill: bookingPill(booking.status) };
  });

  readonly payOpen = signal(false);
  readonly isPaying = signal(false);
  readonly payError = signal<string | null>(null);
  readonly payQr = signal<{ image: string; deeplink?: string; amount: number | string; currency: string } | null>(null);
  selectedMethod = PAYMENT_METHOD_OPTIONS[0].value;
  paymentMethodDetails = signal<Record<string, PaymentMethodDetail>>({});
  readonly methods = PAYMENT_METHOD_OPTIONS.map((m) => m.value);

  readonly methodOptions: SelectOption[] = [...PAYMENT_METHOD_OPTIONS];

  readonly usd = usd;
  readonly prettyDate = prettyDate;
  readonly shortDate = shortDate;
  readonly initials = initials;
  readonly roleLabel = roleLabel;
  readonly bookingPill = bookingPill;

  readonly party = computed<Party | null>(() => {
    const b = this.booking();
    if (!b) return null;
    return this.audience() === 'owner' ? (b.renter as Party) : (b.owner as Party);
  });

  readonly resolvedAt = computed<string | null>(() => {
    const b = this.booking();
    if (!b) return null;
    return b.approved_at || b.rejected_at || b.cancelled_at || null;
  });

  readonly backLink = computed<string>(() =>
    this.audience() === 'owner' ? '/owner/bookings' : '/bookings'
  );

  ngOnInit(): void {
    this.paymentService.getPaymentMethodDetails().subscribe({
      next: (res) => this.paymentMethodDetails.set(res.payment_method_details),
      error: () => undefined,
    });
    this.load();
  }

  selectedPaymentInfo(): PaymentMethodDetail | null {
    return this.paymentMethodDetails()[this.selectedMethod] || null;
  }

  selectPropertyImage(index: number): void {
    this.activePropertyImage.set(index);
  }

  stepPropertyImage(delta: number): void {
    const total = this.propertyImageCount();
    if (!total) return;
    this.activePropertyImage.update(
      (index) => (index + delta + total) % total
    );
  }

  load(): void {
    const rawId = this.id()?.trim() ?? '';
    const idMatch = rawId.match(/^(?:#?BK-)?(\d+)$/i);
    const id = idMatch ? Number(idMatch[1]) : Number(rawId);
    if (!Number.isSafeInteger(id) || id <= 0) {
      this.loadError.set(`Invalid booking reference: ${rawId || 'missing'}`);
      this.isLoading.set(false);
      return;
    }
    this.loadError.set(null);
    this.isLoading.set(true);
    const req = this.auth.isOwner()
      ? this.bookingService.getOwnerBooking(id)
      : this.bookingService.getRenterBooking(id);
    req.subscribe({
      next: (res) => {
        this.booking.set(res.booking as BookingExt);
        this.audience.set(res.audience === 'owner' ? 'owner' : 'renter');
        this.activePropertyImage.set(0);
        this.isLoading.set(false);
      },
      error: (err: HttpErrorResponse) => {
        this.isLoading.set(false);
        this.loadError.set(err.status === 404 ? `Booking not found: ${rawId.startsWith('#') ? rawId.slice(1) : rawId}` : 'Could not load this booking.');
        this.onError(err);
      },
    });
  }

  openRefundChat(refundId: number): void {
    if (!refundId || this.isBusy()) return;
    this.actionError.set(null);
    this.isBusy.set(true);
    this.chat.openRefundChat(refundId).subscribe({
      next: (res) => {
        this.isBusy.set(false);
        void this.router.navigateByUrl(res.url);
      },
      error: (err: HttpErrorResponse) => {
        this.isBusy.set(false);
        this.onError(err);
        if (!this.actionError()) {
          this.actionError.set('Could not open the refund chat. Please try again.');
        }
      },
    });
  }

  private onError(err: HttpErrorResponse): void {
    if (err.status === 403) {
      this.router.navigate(['/denied']);
      return;
    }
    const detail = err.error?.detail;
    if (detail === 'payout_released') {
      this.actionError.set(
        'The 7-day hold has ended, so the rent is due to the owner. This booking can no longer be cancelled automatically.'
      );
    } else if (detail === 'invalid_transition') {
      this.actionError.set('That action is not available for this booking anymore.');
    } else if (typeof detail === 'string' && detail) {
      this.actionError.set(detail.replaceAll('_', ' '));
    }
  }

  private hue(p: Party): number {
    return p.avatar_hue ?? 160;
  }

  avatarBg(p: Party): string {
    return `hsl(${this.hue(p)} 42% 92%)`;
  }

  avatarFg(p: Party): string {
    return `hsl(${this.hue(p)} 55% 28%)`;
  }

  cancel(): void {
    const b = this.booking();
    if (!b) return;
    const message = b.payment_id
      ? window.prompt(this.language.t('bookingDetail.refundMessagePrompt'), '')
      : '';
    if (message === null) return;
    if (b.payment_id && !message.trim()) {
      alert(this.language.t('bookingDetail.refundMessageRequired'));
      return;
    }
    if (!b.payment_id && !confirm(`Cancel this booking request?\n${b.property?.title}`)) return;
    this.actionError.set(null);
    this.isBusy.set(true);
    this.bookingService.cancelBooking(b.id, message).subscribe({
      next: () => {
        this.isBusy.set(false);
        this.load();
      },
      error: (err: HttpErrorResponse) => {
        this.isBusy.set(false);
        this.onError(err);
      },
    });
  }

  ownerCancel(): void {
    const b = this.booking();
    if (!b) return;
    const message = window.prompt(
      this.language.t('bookingDetail.refundMessagePrompt'),
      ''
    );
    if (message === null) return;
    if (!message.trim()) {
      alert(this.language.t('bookingDetail.refundMessageRequired'));
      return;
    }
    this.actionError.set(null);
    this.isBusy.set(true);
    this.bookingService.ownerCancelBooking(b.id, message).subscribe({
      next: () => {
        this.isBusy.set(false);
        this.load();
      },
      error: (err: HttpErrorResponse) => {
        this.isBusy.set(false);
        this.onError(err);
      },
    });
  }

  openPay(): void {
    this.payError.set(null);
    this.payQr.set(null);
    this.payOpen.set(true);
  }

  closePay(): void {
    if (this.isPaying()) return;
    this.payOpen.set(false);
    this.payQr.set(null);
  }

  submitPayment(): void {
    const b = this.booking();
    if (!b) return;
    this.isPaying.set(true);
    this.payError.set(null);
    this.bookingService
      .payBooking(b.id, {
        method: this.selectedMethod,
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
          this.payOpen.set(false);
          this.load();
        },
        error: (err: HttpErrorResponse) => {
          this.isPaying.set(false);
          if (err.status === 403) {
            this.onError(err);
            return;
          }
          if (err.status === 402 || err.error?.detail === 'payment_failed') {
            this.payError.set('Payment failed. Please try again.');
            return;
          }
          const detail = String(err.error?.detail || '');
          if (detail.startsWith('stripe_error')) {
            if (detail.includes('not_configured')) {
              this.payError.set('Stripe is not configured. Add STRIPE_SECRET_KEY to the backend .env and restart.');
            } else {
              this.payError.set('Stripe is unavailable. Please try again.');
            }
            return;
          }
          if (detail === 'unsupported_payment_method') {
            this.payError.set('Choose a supported payment method.');
            return;
          }
          if (detail.startsWith('aba_payway_error')) {
            this.payError.set('ABA PayWay is unavailable. Please try again.');
            return;
          }
          this.payError.set('Payment failed. Please try again.');
        },
      });
  }
}
