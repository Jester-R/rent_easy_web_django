import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { PaymentService, OwnerPaymentsResponse } from '../../../services/payment.service';
import { Payment, Refund } from '../../../models';
import { IconComponent } from '../../../components/icon/icon';

@Component({
  selector: 'app-owner-payments',
  imports: [CommonModule, IconComponent],
  templateUrl: './owner-payments.html',
})
export class OwnerPaymentsComponent implements OnInit {
  private readonly paymentService = inject(PaymentService);

  data = signal<OwnerPaymentsResponse | null>(null);
  isLoading = signal(true);
  actionMessage = signal<string | null>(null);

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
    if (!confirm('Are you sure you want to process this refund?')) return;

    this.actionMessage.set(null);
    this.paymentService.processRefund(refundId).subscribe({
      next: (res) => {
        this.actionMessage.set(`Refund #${res.refund.reference} has been processed.`);
        this.loadPayments();
      },
    });
  }
}
