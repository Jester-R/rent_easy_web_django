import { Component, computed, inject, OnDestroy, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { ConsoleService } from '../../../services/console.service';
import { IconComponent } from '../../../components/icon/icon';
import { Payment, Refund } from '../../../models';
import {
  methodIcon,
  methodLabel,
  paymentPill,
  paymentStatusLabel,
  refundPill,
  refundReasonLabel,
  refundStatusLabel,
  shortDate,
  usd,
} from '../../../shared/ui';

@Component({
  selector: 'app-console-payments',
  imports: [CommonModule, RouterLink, IconComponent],
  templateUrl: './console-payments.html',
})
export class ConsolePaymentsComponent implements OnInit, OnDestroy {
  private readonly console = inject(ConsoleService);

  readonly methodIcon = methodIcon;
  readonly methodLabel = methodLabel;
  readonly paymentPill = paymentPill;
  readonly paymentStatusLabel = paymentStatusLabel;
  readonly refundPill = refundPill;
  readonly refundReasonLabel = refundReasonLabel;
  readonly refundStatusLabel = refundStatusLabel;
  readonly shortDate = shortDate;
  readonly usd = usd;

  payments = signal<Payment[]>([]);
  refunds = signal<Refund[]>([]);
  total = signal(0);
  revenue = signal(0);
  statusCounts = signal<Record<string, number>>({});
  query = signal('');
  status = signal('all');
  isLoading = signal(true);
  error = signal<string | null>(null);
  selected = signal<number[]>([]);

  private timer: ReturnType<typeof setTimeout> | null = null;

  pendingRefunds = computed(() => this.refunds().filter((r) => r.status === 'Pending').length);

  allSelected = computed(() => {
    const list = this.payments();
    return list.length > 0 && list.every((p) => this.selected().includes(p.id));
  });

  statusOptions = computed(() => {
    const c = this.statusCounts();
    return [
      { value: 'all', label: `All (${c['all'] ?? 0})` },
      { value: 'Success', label: `Success (${c['Success'] ?? 0})` },
      { value: 'Failed', label: `Failed (${c['Failed'] ?? 0})` },
      { value: 'Refunded', label: `Refunded (${c['Refunded'] ?? 0})` },
    ];
  });

  ngOnInit(): void {
    this.load();
  }

  ngOnDestroy(): void {
    if (this.timer) clearTimeout(this.timer);
  }

  load(): void {
    this.isLoading.set(true);
    this.console.getPayments({ q: this.query(), status: this.status() }).subscribe({
      next: (res) => {
        this.payments.set(res.payments);
        this.refunds.set(res.refunds);
        this.total.set(res.total);
        this.revenue.set(res.revenue);
        this.statusCounts.set(res.status_counts);
        this.selected.set([]);
        this.error.set(null);
        this.isLoading.set(false);
      },
      error: () => this.isLoading.set(false),
    });
  }

  onSearch(value: string): void {
    this.query.set(value);
    if (this.timer) clearTimeout(this.timer);
    this.timer = setTimeout(() => this.load(), 550);
  }

  onStatusChange(value: string): void {
    this.status.set(value);
    if (this.timer) clearTimeout(this.timer);
    this.load();
  }

  applyFilter(): void {
    if (this.timer) clearTimeout(this.timer);
    this.load();
  }

  refresh(): void {
    this.query.set('');
    this.status.set('all');
    if (this.timer) clearTimeout(this.timer);
    this.load();
  }

  isSelected(id: number): boolean {
    return this.selected().includes(id);
  }

  toggle(id: number): void {
    const cur = this.selected();
    this.selected.set(cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]);
  }

  toggleAll(): void {
    this.selected.set(this.allSelected() ? [] : this.payments().map((p) => p.id));
  }

  clearSelection(): void {
    this.selected.set([]);
  }

  refund(p: Payment): void {
    if (!confirm(`Issue a refund?\n\n${p.reference} — ${usd(p.amount)}`)) return;
    this.console.createRefund({ payment: p.id, reason: 'other' }).subscribe({
      next: () => this.load(),
      error: (err) => this.setError(err, 'Failed to issue refund.'),
    });
  }

  removePayment(p: Payment): void {
    if (!confirm(`Delete this record? This cannot be undone?\n\n${p.reference}`)) return;
    this.console.deletePayment(p.id).subscribe({
      next: () => this.load(),
      error: (err) => this.setError(err, 'Failed to delete payment.'),
    });
  }

  bulkDelete(): void {
    const ids = this.selected();
    if (!ids.length) return;
    if (!confirm(`Delete this record? This cannot be undone?\n\n${ids.length} records`)) return;
    this.console.bulkDeletePayments(ids).subscribe({
      next: () => this.load(),
      error: (err) => this.setError(err, 'Failed to delete payments.'),
    });
  }

  process(r: Refund): void {
    if (!confirm('Process this refund?')) return;
    this.console.processRefund(r.id).subscribe({
      next: () => this.load(),
      error: (err) => this.setError(err, 'Failed to process refund.'),
    });
  }

  private setError(err: unknown, fallback: string): void {
    const detail = (err as { error?: { detail?: string } }).error?.detail;
    this.error.set(detail || fallback);
  }
}