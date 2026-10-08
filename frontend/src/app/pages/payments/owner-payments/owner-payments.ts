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
    const khmer: Record<string, string> = {
      Success: 'ជោគជ័យ', Pending: 'កំពុងរង់ចាំ', Failed: 'បរាជ័យ', Refunded: 'បានសងប្រាក់វិញ',
    };
    return this.language.current() === 'km' ? (khmer[status] ?? status) : status;
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
    if (!confirm(this.language.t('Are you sure you want to process this refund?', 'តើអ្នកប្រាកដថាចង់ដំណើរការការសងប្រាក់វិញនេះឬទេ?'))) return;

    this.actionMessage.set(null);
    this.paymentService.processRefund(refundId).subscribe({
      next: (res) => {
        this.actionMessage.set(this.language.t(
          `Refund #${res.refund.reference} has been processed.`,
          `ការសងប្រាក់វិញ #${res.refund.reference} ត្រូវបានដំណើរការរួចរាល់។`,
        ));
        this.loadPayments();
      },
    });
  }
}
