import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { PaymentService, OwnerPaymentsResponse } from '../../../services/payment.service';
import { Payment } from '../../../models';
import { IconComponent } from '../../../components/icon/icon';
import { DataPaginationComponent } from '../../../components/data-pagination/data-pagination';
import { LanguageService } from '../../../services/language.service';
import { payoutMethodLabel, payoutPill, refundReasonLabel } from '../../../shared/ui';

@Component({
  selector: 'app-owner-payments',
  imports: [CommonModule, FormsModule, RouterLink, IconComponent, DataPaginationComponent],
  templateUrl: './owner-payments.html',
})
export class OwnerPaymentsComponent implements OnInit {
  private readonly paymentService = inject(PaymentService);
  readonly language = inject(LanguageService);
  readonly payoutPill = payoutPill;
  readonly payoutMethodLabel = payoutMethodLabel;
  readonly refundReasonLabel = refundReasonLabel;

  data = signal<OwnerPaymentsResponse | null>(null);
  page = signal(1);
  readonly pageSize = 25;
  payoutPage = signal(1);
  refundPage = signal(1);
  searchTerm = '';
  isLoading = signal(true);

  statusLabel(status: string): string {
    return this.language.valueLabel(status);
  }

  ngOnInit(): void {
    this.loadPayments();
  }

  loadPayments(): void {
    this.isLoading.set(true);
    this.paymentService.getOwnerPayments({
      q: this.searchTerm,
      page: this.page(), page_size: this.pageSize,
      payout_page: this.payoutPage(), payout_page_size: this.pageSize,
      refund_page: this.refundPage(), refund_page_size: this.pageSize,
    }).subscribe({
      next: (res) => {
        this.data.set(res);
        this.page.set(res.page);
        this.isLoading.set(false);
      },
      error: () => this.isLoading.set(false),
    });
  }

  applySearch(): void {
    this.page.set(1);
    this.loadPayments();
  }

  changePage(page: number): void {
    this.page.set(page);
    this.loadPayments();
  }

  changePayoutPage(page: number): void {
    this.payoutPage.set(page);
    this.loadPayments();
  }

  changeRefundPage(page: number): void {
    this.refundPage.set(page);
    this.loadPayments();
  }

}
