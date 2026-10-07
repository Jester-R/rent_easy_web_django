import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { PaymentService, RenterPaymentsResponse } from '../../../services/payment.service';
import { Payment } from '../../../models';
import { IconComponent } from '../../../components/icon/icon';

@Component({
  selector: 'app-renter-payments',
  imports: [CommonModule, FormsModule, IconComponent],
  templateUrl: './renter-payments.html',
})
export class RenterPaymentsComponent implements OnInit {
  private readonly paymentService = inject(PaymentService);

  payments = signal<Payment[]>([]);
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
      })
      .subscribe({
        next: (res: RenterPaymentsResponse) => {
          this.payments.set(res.payments);
          this.isLoading.set(false);
        },
        error: () => this.isLoading.set(false),
      });
  }
}
