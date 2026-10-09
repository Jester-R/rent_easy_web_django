import { Component, computed, inject, OnDestroy, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ConsoleService } from '../../../services/console.service';
import { LanguageService } from '../../../services/language.service';
import { IconComponent } from '../../../components/icon/icon';
import {
  SearchableSelectComponent,
  SelectOption,
} from '../../../components/searchable-select/searchable-select';
import { Payment, Refund } from '../../../models';
import {
  PAYMENT_METHODS,
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
  imports: [CommonModule, FormsModule, IconComponent, SearchableSelectComponent],
  templateUrl: './console-payments.html',
})
export class ConsolePaymentsComponent implements OnInit, OnDestroy {
  readonly language = inject(LanguageService);
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

  statusText(value: string): string {
    const khmer: Record<string, string> = {
      Successful: 'ជោគជ័យ', Failed: 'បរាជ័យ', Pending: 'កំពុងរង់ចាំ',
      'No Refund': 'មិនមានការសងប្រាក់ទេ', Processed: 'បានដំណើរការ',
    };
    return this.language.current() === 'km' ? (khmer[value] ?? value) : value;
  }

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

  readonly methods = PAYMENT_METHODS;
  readonly paymentStatuses = ['Success', 'Failed'];
  readonly refundStatuses = ['None', 'Pending', 'Processed'];

  readonly methodOptions: SelectOption[] = PAYMENT_METHODS.map((m) => ({ value: m, label: m }));
  readonly paymentStatusOptions: SelectOption[] = this.paymentStatuses.map((s) => ({
    value: s,
    label: this.statusText(this.paymentStatusLabel(s)),
  }));
  readonly refundStatusOptions: SelectOption[] = this.refundStatuses.map((s) => ({
    value: s,
    label: this.statusText(this.refundStatusLabel(s)),
  }));

  editing = signal<Payment | null>(null);
  isSaving = signal(false);
  editForm = { amount: 0, method: PAYMENT_METHODS[0], status: 'Success', refund_status: 'None' };

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

  readonly statusSelectOptions = computed<SelectOption[]>(() =>
    this.statusOptions().map((o) => ({ value: o.value, label: o.label }))
  );

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

  openEdit(p: Payment): void {
    this.editForm = {
      amount: p.amount,
      method: p.method,
      status: p.status,
      refund_status: p.refund_status,
    };
    this.editing.set(p);
  }

  closeEdit(): void {
    if (this.isSaving()) return;
    this.editing.set(null);
  }

  saveEdit(): void {
    const p = this.editing();
    if (!p) return;
    this.isSaving.set(true);
    this.console
      .updatePayment(p.id, {
        amount: Number(this.editForm.amount),
        method: this.editForm.method,
        status: this.editForm.status,
        refund_status: this.editForm.refund_status,
      })
      .subscribe({
        next: () => {
          this.isSaving.set(false);
          this.editing.set(null);
          this.load();
        },
        error: (err) => {
          this.isSaving.set(false);
          this.setError(err, 'Failed to update payment.');
        },
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
