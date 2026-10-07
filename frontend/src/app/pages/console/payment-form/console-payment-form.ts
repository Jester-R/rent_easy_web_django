import { Component, inject, input, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { ConsoleService } from '../../../services/console.service';
import { IconComponent } from '../../../components/icon/icon';
import { Booking, ConsolePropertyItem, ConsoleUserItem, Payment } from '../../../models';
import { prettyDate } from '../../../shared/ui';

@Component({
  selector: 'app-console-payment-form',
  imports: [CommonModule, ReactiveFormsModule, RouterLink, IconComponent],
  templateUrl: './console-payment-form.html',
})
export class ConsolePaymentFormComponent implements OnInit {
  readonly id = input<string>();

  private readonly fb = inject(FormBuilder);
  private readonly console = inject(ConsoleService);
  private readonly router = inject(Router);

  readonly prettyDate = prettyDate;

  methods = ['ABA Pay (Mock)', 'Wing (Mock)', 'Credit Card (Mock)'];

  isEdit = signal(false);
  isLoading = signal(true);
  isSaving = signal(false);
  submitted = signal(false);
  error = signal<string | null>(null);
  payment = signal<Payment | null>(null);
  properties = signal<ConsolePropertyItem[]>([]);
  bookings = signal<Booking[]>([]);
  users = signal<ConsoleUserItem[]>([]);

  form = this.fb.group({
    property: [null as number | null],
    booking: [null as number | null],
    user: [null as number | null],
    amount: [0, [Validators.required, Validators.min(0)]],
    method: ['ABA Pay (Mock)'],
    status: ['Success'],
    refund_status: ['None'],
    refunded_amount: [0, [Validators.min(0)]],
  });

  ngOnInit(): void {
    if (this.id()) {
      this.isEdit.set(true);
      this.loadPayment(Number(this.id()));
    } else {
      this.isLoading.set(false);
      this.loadDropdowns();
    }
  }

  loadDropdowns(): void {
    this.console.getProperties({}).subscribe({
      next: (res) => this.properties.set(res.properties),
    });
    this.console.getBookings({}).subscribe({
      next: (res) => this.bookings.set(res.bookings),
    });
    this.console.getUsers({}).subscribe({
      next: (res) => this.users.set(res.users),
    });
  }

  loadPayment(id: number): void {
    this.isLoading.set(true);
    this.console.getPayments({}).subscribe({
      next: (res) => {
        this.isLoading.set(false);
        const p = res.payments.find((x) => x.id === id);
        if (!p) {
          this.error.set('Payment not found.');
          return;
        }
        this.payment.set(p);
        this.form.patchValue({
          amount: p.amount,
          method: p.method,
          status: p.status,
          refund_status: p.refund_status,
          refunded_amount: p.refunded_amount,
        });
      },
      error: () => {
        this.isLoading.set(false);
        this.error.set('Failed to load payment.');
      },
    });
  }

  onSubmit(): void {
    this.submitted.set(true);
    this.error.set(null);
    if (this.id()) {
      this.saveEdit();
    } else {
      this.saveCreate();
    }
  }

  saveCreate(): void {
    const v = this.form.value;
    if (!v.user) {
      this.error.set('User and amount are required.');
      return;
    }
    this.isSaving.set(true);
    const payload: Record<string, unknown> = {
      user: Number(v.user),
      amount: Number(v.amount) || 0,
      method: v.method || 'ABA Pay (Mock)',
      status: v.status || 'Success',
    };
    if (v.property) payload['property'] = Number(v.property);
    if (v.booking) payload['booking'] = Number(v.booking);
    this.console.createPayment(payload).subscribe({
      next: () => {
        this.isSaving.set(false);
        this.router.navigate(['/console/payments']);
      },
      error: (err) => {
        this.isSaving.set(false);
        this.mapError(err);
      },
    });
  }

  saveEdit(): void {
    const v = this.form.value;
    this.isSaving.set(true);
    const payload: Record<string, unknown> = {
      amount: Number(v.amount) || 0,
      method: v.method || 'ABA Pay (Mock)',
      status: v.status || 'Success',
      refund_status: v.refund_status || 'None',
      refunded_amount: Number(v.refunded_amount) || 0,
    };
    this.console.updatePayment(Number(this.id()), payload).subscribe({
      next: () => {
        this.isSaving.set(false);
        this.router.navigate(['/console/payments']);
      },
      error: (err) => {
        this.isSaving.set(false);
        this.mapError(err);
      },
    });
  }

  private mapError(err: unknown): void {
    const key = (err as { error?: { detail?: string } }).error?.detail;
    const messages: Record<string, string> = {
      user_and_amount_required: 'User and amount are required.',
    };
    this.error.set((key && messages[key]) || 'Failed to save payment.');
  }
}