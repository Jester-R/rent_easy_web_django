import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { PaymentService, OwnerPaymentsResponse } from '../../../services/payment.service';
import { Payment, Refund } from '../../../models';
import { IconComponent } from '../../../components/icon/icon';
import { LanguageService } from '../../../services/language.service';

@Component({
  selector: 'app-owner-payments',
  imports: [CommonModule, IconComponent],
  templateUrl: './owner-payments.html',
})
export class OwnerPaymentsComponent implements OnInit {
  private readonly paymentService = inject(PaymentService);
  readonly language = inject(LanguageService);

  data = signal<OwnerPaymentsResponse | null>(null);
  isLoading = signal(true);
  actionMessage = signal<string | null>(null);

  statusLabel(status: string): string {
    return this.language.valueLabel(status);
  }

  ngOnInit(): void {
    this.loadPayments();
  }

  loadPayments(): void {
    this.isLoading.set(true);
    this.paymentService.getOwnerPayments().subscribe({
      next: (res) => {
        this.data.set(res);
        this.isLoading.set(false);
      },
      error: () => this.isLoading.set(false),
    });
  }

  processRefund(refundId: number): void {
    if (!confirm(this.language.t('ownerPayments.areYouSureYouWantToProcessThisRefund'))) return;

    this.actionMessage.set(null);
    this.paymentService.processRefund(refundId).subscribe({
      next: (res) => {
        this.actionMessage.set(this.language.t('ownerPayments.refundProcessed', { reference: res.refund.reference }));
        this.loadPayments();
      },
    });
  }
}
