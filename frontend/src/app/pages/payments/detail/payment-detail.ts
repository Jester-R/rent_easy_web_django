import { Component, OnInit, inject, input, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { HttpErrorResponse } from '@angular/common/http';
import { IconComponent } from '../../../components/icon/icon';
import { AuthService } from '../../../services/auth.service';
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
export class PaymentDetailComponent implements OnInit {
  readonly id = input<string>();

  private readonly paymentService = inject(PaymentService);
  private readonly router = inject(Router);
  readonly auth = inject(AuthService);

  readonly payment = signal<Payment | null>(null);
  readonly audience = signal<'renter' | 'owner'>('renter');
  readonly refund = signal<Refund | null>(null);
  readonly isLoading = signal(true);
  readonly isProcessing = signal(false);
  readonly copied = signal(false);

  readonly usd = usd;
  readonly prettyDate = prettyDate;
  readonly shortDate = shortDate;
  readonly methodIcon = methodIcon;
  readonly methodLabel = methodLabel;
  readonly paymentStatusLabel = paymentStatusLabel;
  readonly refundStatusLabel = refundStatusLabel;
  readonly refundPill = refundPill;

  ngOnInit(): void {
    this.load();
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
        this.loadRefund(res.payment);
      },
      error: (err: HttpErrorResponse) => {
        this.isLoading.set(false);
        this.onError(err);
      },
    });
  }

  private loadRefund(p: Payment): void {
    this.refund.set(null);
    if (this.audience() !== 'owner' || p.refund_status === 'None') return;
    this.paymentService.getOwnerPayments().subscribe({
      next: (res) => {
        this.refund.set(res.pending_refunds.find((r) => r.payment_id === p.id) ?? null);
      },
      error: () => undefined,
    });
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

  processRefund(): void {
    const p = this.payment();
    const r = this.refund();
    if (!p || !r) return;
    if (!confirm(`Process this refund?\n${usd(r.amount)} · ${p.reference}`)) return;
    this.isProcessing.set(true);
    this.paymentService.processRefund(r.id).subscribe({
      next: () => {
        this.isProcessing.set(false);
        this.load();
      },
      error: (err: HttpErrorResponse) => {
        this.isProcessing.set(false);
        this.onError(err);
      },
    });
  }
}