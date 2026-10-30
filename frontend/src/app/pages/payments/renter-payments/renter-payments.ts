import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { PaymentService, RenterPaymentsResponse } from '../../../services/payment.service';
import { Payment } from '../../../models';
import { IconComponent } from '../../../components/icon/icon';
import { DataPaginationComponent } from '../../../components/data-pagination/data-pagination';
import { LanguageService } from '../../../services/language.service';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-renter-payments',
  imports: [CommonModule, FormsModule, IconComponent, RouterLink, DataPaginationComponent],
  templateUrl: './renter-payments.html',
})
export class RenterPaymentsComponent implements OnInit {
  readonly language = inject(LanguageService);
  private readonly paymentService = inject(PaymentService);

  payments = signal<Payment[]>([]);
  total = signal(0);
  page = signal(1);
  readonly pageSize = 25;
  isLoading = signal(true);
  searchTerm = '';
  selectedStatus = 'all';

  ngOnInit(): void {
    this.loadPayments();
  }

  loadPayments(): void {
    this.isLoading.set(true);
    this.paymentService
      .getRenterPayments({
        q: this.searchTerm,
        status: this.selectedStatus,
        page: this.page(),
        page_size: this.pageSize,
      })
      .subscribe({
        next: (res: RenterPaymentsResponse) => {
          this.payments.set(res.payments);
          this.total.set(res.total);
          this.page.set(res.page);
          this.isLoading.set(false);
        },
        error: () => this.isLoading.set(false),
      });
  }

  changePage(page: number): void {
    this.page.set(page);
    this.loadPayments();
  }

  applyFilters(): void {
    this.page.set(1);
    this.loadPayments();
  }
}
