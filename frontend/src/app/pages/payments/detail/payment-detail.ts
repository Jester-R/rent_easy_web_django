import { Component, OnDestroy, OnInit, inject, input, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { HttpErrorResponse } from '@angular/common/http';
import { IconComponent } from '../../../components/icon/icon';
import { AuthService } from '../../../services/auth.service';
import { LanguageService } from '../../../services/language.service';
import { PaymentService } from '../../../services/payment.service';
import { Payment, Refund } from '../../../models';
import {
  methodIcon,
  methodLabel,
  paymentStatusLabel,
  prettyDate,
  refundPill,
  refundStatusLabel,
  shortDate,
  usd,
} from '../../../shared/ui';

@Component({
  selector: 'app-payment-detail',
  imports: [RouterLink, IconComponent],
  templateUrl: './payment-detail.html',
})
export class PaymentDetailComponent implements OnInit, OnDestroy {
  readonly id = input<string>();

  private readonly paymentService = inject(PaymentService);
  private readonly router = inject(Router);
  readonly auth = inject(AuthService);
  readonly language = inject(LanguageService);

  readonly payment = signal<Payment | null>(null);
  readonly audience = signal<'renter' | 'owner'>('renter');
  readonly refund = signal<Refund | null>(null);
  readonly showRefundRequest = signal(false);
  readonly refundReason = signal('other');
  readonly refundRequestNote = signal('');
  readonly isRequestingRefund = signal(false);
  readonly refundRequestMessage = signal<string | null>(null);
  readonly refundRequestError = signal<string | null>(null);
  readonly isLoading = signal(true);
  readonly isRefreshing = signal(false);
  readonly refreshError = signal<string | null>(null);
  readonly copied = signal(false);

  private pollTimer: ReturnType<typeof setTimeout> | null = null;
  private pollAttempts = 0;
  private readonly maxPollAttempts = 20;

  readonly usd = usd;
  readonly prettyDate = prettyDate;
  readonly shortDate = shortDate;
  readonly methodIcon = methodIcon;
  readonly methodLabel = methodLabel;
  readonly paymentStatusLabel = paymentStatusLabel;
  readonly refundStatusLabel = refundStatusLabel;
  readonly refundPill = refundPill;

  renterRefundWindowOpen(payment: Payment): boolean {
    const paidAt = payment.paid_at || payment.created_at;
    const paidTime = Date.parse(paidAt);
    return !Number.isFinite(paidTime) || Date.now() < paidTime + 7 * 24 * 60 * 60 * 1000;
  }

  ngOnInit(): void {
    this.load();
  }

  ngOnDestroy(): void {
    this.stopPolling();
  }

  load(): void {
    const id = Number(this.id());
    if (!id) {
      this.isLoading.set(false);
      return;
    }
    this.isLoading.set(true);
    const req = this.auth.isOwner()
      ? this.paymentService.getOwnerPayment(id)
      : this.paymentService.getRenterPayment(id);
    req.subscribe({
      next: (res) => {
        this.payment.set(res.payment);
        this.audience.set(res.audience === 'owner' ? 'owner' : 'renter');
        this.isLoading.set(false);
        this.refund.set(res.refund ?? null);
        if (res.payment.status === 'Pending' && res.payment.provider === 'aba_payway') {
          this.startPolling();
        }
      },
      error: (err: HttpErrorResponse) => {
        this.isLoading.set(false);
        this.onError(err);
      },
    });
  }

  /** Check PayWay for a pending transaction and keep polling for a short while. */
  refreshPayment(silent = false): void {
    const p = this.payment();
    if (!p || p.status !== 'Pending' || this.isRefreshing()) return;
    if (!silent) this.refreshError.set(null);
    this.isRefreshing.set(true);
    const req = this.audience() === 'owner'
      ? this.paymentService.refreshOwnerPayment(p.id)
      : this.paymentService.refreshRenterPayment(p.id);
    req.subscribe({
      next: (res) => {
        this.isRefreshing.set(false);
        this.payment.set(res.payment);
        if (res.payment.status === 'Pending') {
          this.schedulePoll();
        } else {
          this.stopPolling();
          if (this.audience() === 'owner' && res.payment.refund_status === 'None') {
            this.refund.set(null);
          }
        }
      },
      error: () => {
        this.isRefreshing.set(false);
        this.refreshError.set('Could not reach ABA PayWay. Try again shortly.');
        this.schedulePoll();
      },
    });
  }

  private startPolling(): void {
    this.stopPolling();
    this.pollAttempts = 0;
    this.schedulePoll();
  }

  private schedulePoll(): void {
    if (this.pollTimer !== null) return;
    if (this.pollAttempts >= this.maxPollAttempts) {
      this.stopPolling();
      return;
    }
    this.pollAttempts += 1;
    this.pollTimer = setTimeout(() => {
      this.pollTimer = null;
      this.refreshPayment(true);
    }, 3000);
  }

  private stopPolling(): void {
    if (this.pollTimer !== null) {
      clearTimeout(this.pollTimer);
      this.pollTimer = null;
    }
  }

  private onError(err: HttpErrorResponse): void {
    if (err.status === 403) {
      this.router.navigate(['/denied']);
    }
  }

  copyReference(): void {
    const p = this.payment();
    if (!p) return;
    this.copied.set(false);
    void navigator.clipboard.writeText(p.reference).then(() => {
      this.copied.set(true);
      setTimeout(() => this.copied.set(false), 1500);
    });
  }

  submitRefundRequest(): void {
    const payment = this.payment();
    const requestNote = this.refundRequestNote().trim();
    if (!payment || !requestNote) {
      this.refundRequestError.set(this.language.t('ownerPayments.refundDetailsRequired'));
      return;
    }
    this.isRequestingRefund.set(true);
    this.refundRequestError.set(null);
    this.refundRequestMessage.set(null);
    this.paymentService.requestRefund(payment.id, {
      reason: this.refundReason(),
      request_note: requestNote,
    }).subscribe({
      next: (res) => {
        this.refund.set(res.refund);
        this.payment.update((current) => current ? { ...current, refund_status: 'Pending' } : current);
        this.showRefundRequest.set(false);
        this.refundRequestNote.set('');
        this.refundRequestMessage.set(this.language.t('ownerPayments.refundRequestSent'));
        this.isRequestingRefund.set(false);
      },
      error: (err: HttpErrorResponse) => {
        const detail = err.error?.detail;
        const messages: Record<string, string> = {
          refund_already_pending: 'A refund request is already under review.',
          refund_already_processed: 'This payment has already been refunded.',
          payment_not_refundable: 'Only successful payments can be submitted for refund review.',
          refund_window_closed: 'Renter refund requests must be submitted within 7 days of payment.',
        };
        this.refundRequestError.set(messages[detail] || 'Could not submit the refund request. Please try again.');
        this.isRequestingRefund.set(false);
      },
    });
  }

}
