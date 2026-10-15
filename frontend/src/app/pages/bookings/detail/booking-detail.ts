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
import { LanguageService } from '../../../services/language.service';
import { propertyLocation, propertyTitle } from '../../../shared/property-text';
import type { Property } from '../../../models';
import { Booking, UserBrief } from '../../../models';
import {
  PAYMENT_METHODS,
  bookingPill,
  initials,
  prettyDate,
  roleLabel,
  shortDate,
  submitHostedCheckout,
  usd,
} from '../../../shared/ui';

type Party = UserBrief & { avatar_hue?: number };
type BookingExt = Booking & { can_approve?: boolean; can_cancel?: boolean; can_reject?: boolean };

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
  readonly id = input<string>();

  private readonly bookingService = inject(BookingService);
  private readonly router = inject(Router);
  readonly auth = inject(AuthService);

  readonly booking = signal<BookingExt | null>(null);
  readonly loadError = signal<string | null>(null);
  readonly audience = signal<'renter' | 'owner'>('renter');
  readonly isLoading = signal(true);
  readonly isBusy = signal(false);
  readonly actionError = signal<string | null>(null);

  readonly payOpen = signal(false);
  readonly isPaying = signal(false);
  readonly payError = signal<string | null>(null);
  selectedMethod = PAYMENT_METHODS[0];
  readonly methods = PAYMENT_METHODS;

  readonly methodOptions: SelectOption[] = this.methods.map((m) => ({ value: m, label: m }));

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
    this.load();
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
        this.isLoading.set(false);
      },
      error: (err: HttpErrorResponse) => {
        this.isLoading.set(false);
        this.loadError.set(err.status === 404 ? `Booking not found: ${rawId.startsWith('#') ? rawId.slice(1) : rawId}` : 'Could not load this booking.');
        this.onError(err);
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

  approve(): void {
    const b = this.booking();
    if (!b) return;
    if (!confirm(`Approve Booking Request?\n${b.renter.display_name} · ${b.property?.title}`)) return;
    this.isBusy.set(true);
    this.bookingService.approveBooking(b.id).subscribe({
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

  reject(): void {
    const b = this.booking();
    if (!b) return;
    if (!confirm(`Reject Booking Request?\n${b.renter.display_name} · ${b.property?.title}`)) return;
    this.isBusy.set(true);
    this.bookingService.rejectBooking(b.id).subscribe({
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

  cancel(): void {
    const b = this.booking();
    if (!b) return;
    const paidWarning = b.payment_id
      ? '\n\nA refund request will be sent to the admin team for review.'
      : '';
    if (!confirm(`Cancel this booking request?\n${b.property?.title}${paidWarning}`)) return;
    this.actionError.set(null);
    this.isBusy.set(true);
    this.bookingService.cancelBooking(b.id).subscribe({
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
    if (
      !confirm(
        `Cancel this paid booking?\n${b.renter.display_name} · ${b.property?.title}\n\nA refund request will be sent to the admin team for review.`
      )
    )
      return;
    this.actionError.set(null);
    this.isBusy.set(true);
    this.bookingService.ownerCancelBooking(b.id).subscribe({
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
    this.payOpen.set(true);
  }

  closePay(): void {
    if (this.isPaying()) return;
    this.payOpen.set(false);
  }

  submitPayment(): void {
    const b = this.booking();
    if (!b) return;
    this.isPaying.set(true);
    this.payError.set(null);
    this.bookingService
      .payBooking(b.id, {
        method: this.selectedMethod,
        simulate: this.selectedMethod.includes('(Mock)') ? 'success' : undefined,
      })
      .subscribe({
        next: (res) => {
          if (res.checkout) {
            submitHostedCheckout(res.checkout);
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
          if (String(err.error?.detail || '').startsWith('aba_payway_error')) {
            this.payError.set('ABA PayWay is unavailable. Please try again.');
            return;
          }
          this.payError.set('Payment failed. Please try again.');
        },
      });
  }
}
