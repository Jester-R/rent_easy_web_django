import { Component, computed, inject, OnDestroy, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { CommonModule } from '@angular/common';
import { Subscription } from 'rxjs';
import { FormsModule } from '@angular/forms';
import { ChatService } from '../../../services/chat.service';
import { ConsoleService } from '../../../services/console.service';
import { LanguageService } from '../../../services/language.service';
import { IconComponent } from '../../../components/icon/icon';
import { DataPaginationComponent } from '../../../components/data-pagination/data-pagination';
import {
  SearchableSelectComponent,
  SelectOption,
} from '../../../components/searchable-select/searchable-select';
import { Payment, Payout, PayoutTotals, Refund } from '../../../models';
import {
  methodIcon,
  methodLabel,
  paymentPill,
  paymentStatusLabel,
  payoutMethodLabel,
  payoutPill,
  refundPill,
  refundReasonLabel,
  refundStatusLabel,
  shortDate,
  usd,
} from '../../../shared/ui';

@Component({
  selector: 'app-console-payments',
  imports: [CommonModule, FormsModule, RouterLink, IconComponent, SearchableSelectComponent, DataPaginationComponent],
  templateUrl: './console-payments.html',
})
export class ConsolePaymentsComponent implements OnInit, OnDestroy {
  readonly language = inject(LanguageService);
  private readonly chat = inject(ChatService);
  private readonly console = inject(ConsoleService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);

  readonly section = signal<'payments' | 'payouts' | 'refunds' | 'settings'>('payments');

  readonly methodIcon = methodIcon;
  readonly methodLabel = methodLabel;
  readonly paymentPill = paymentPill;
  readonly paymentStatusLabel = paymentStatusLabel;
  readonly payoutMethodLabel = payoutMethodLabel;
  readonly payoutPill = payoutPill;
  readonly refundPill = refundPill;
  readonly refundReasonLabel = refundReasonLabel;
  readonly refundStatusLabel = refundStatusLabel;
  readonly shortDate = shortDate;
  readonly usd = usd;

  statusText(value: string): string {
    return this.language.valueLabel(value);
  }

  sectionTitle(): string {
    switch (this.section()) {
      case 'payouts':
        return this.language.t('consolePayments.ownerPayouts');
      case 'refunds':
        return this.language.t('consolePayments.recentRefunds');
      case 'settings':
        return this.language.t('consoleSettings.paymentCommissions');
      default:
        return this.language.t('consolePayments.payments');
    }
  }

  payments = signal<Payment[]>([]);
  refunds = signal<Refund[]>([]);
  payouts = signal<Payout[]>([]);
  selectedPayout = signal<Payout | null>(null);
  payoutTotals = signal<PayoutTotals>({ scheduled: 0, eligible: 0, paid: 0 });
  total = signal(0);
  page = signal(1);
  readonly pageSize = 25;
  payoutPage = signal(1);
  readonly payoutPageSize = 25;
  payoutsTotal = signal(0);
  refundPage = signal(1);
  readonly refundPageSize = 25;
  refundsTotal = signal(0);
  refundStatus = signal('all');
  revenue = signal(0);
  statusCounts = signal<Record<string, number>>({});
  query = signal('');
  status = signal('all');
  isLoading = signal(true);
  error = signal<string | null>(null);
  isSaving = signal(false);
  commissionRates = signal<Record<string, number>>({});
  lateCancellationFee = signal(0);
  commissionSaving = signal(false);
  commissionError = signal<string | null>(null);
  commissionSaved = signal(false);

  private timer: ReturnType<typeof setTimeout> | null = null;
  private readonly routeSub = new Subscription();

  pendingRefunds = computed(() => this.refunds().filter((r) => r.status === 'Pending').length);
  eligiblePayouts = computed(() => this.payouts().filter((p) => p.status === 'Eligible'));
  eligiblePayoutTotal = computed(() =>
    this.eligiblePayouts().reduce((sum, payout) => sum + Number(payout.amount || 0), 0)
  );

  statusOptions = computed(() => {
    const c = this.statusCounts();
    return [
      { value: 'all', label: `All (${c['all'] ?? 0})` },
      { value: 'Success', label: `Success (${c['Success'] ?? 0})` },
      { value: 'Pending', label: `Pending (${c['Pending'] ?? 0})` },
      { value: 'Failed', label: `Failed (${c['Failed'] ?? 0})` },
      { value: 'Refunded', label: `Refunded (${c['Refunded'] ?? 0})` },
    ];
  });

  readonly statusSelectOptions = computed<SelectOption[]>(() =>
    this.statusOptions().map((o) => ({ value: o.value, label: o.label }))
  );

  ngOnInit(): void {
    let initial = true;
    this.routeSub.add(
      this.route.data.subscribe((data) => {
        const routeSection = data['section'];
        const section =
          routeSection === 'payouts' || routeSection === 'refunds' || routeSection === 'settings'
            ? routeSection
            : 'payments';
        const changed = section !== this.section();
        this.section.set(section);
        if (initial) {
          initial = false;
          this.load();
          if (section === 'settings') this.loadSettings();
          return;
        }
        if (changed) {
          this.load();
          if (section === 'settings') this.loadSettings();
        }
      }),
    );
  }

  private loadSettings(): void {
    this.console.getSettings().subscribe({
      next: (res) => {
        this.commissionRates.set(res.settings.commission_rates || {});
        this.lateCancellationFee.set(Number(res.settings.late_cancellation_fee || 0));
      },
      error: () => this.commissionError.set(this.language.t('consoleSettings.failedToLoadSettings')),
    });
  }

  updateCommissionRate(value: string): void {
    const rate = Number(value);
    this.commissionRates.update((rates) => ({ ...rates, 'ABA Pay': Number.isFinite(rate) ? rate : 0 }));
    this.commissionSaved.set(false);
  }

  updateLateCancellationFee(value: string): void {
    const fee = Number(value);
    this.lateCancellationFee.set(Number.isFinite(fee) && fee >= 0 ? fee : 0);
    this.commissionSaved.set(false);
  }

  saveCommissionRate(): void {
    this.commissionSaving.set(true);
    this.commissionError.set(null);
    this.commissionSaved.set(false);
    this.console
      .updateSettings({
        commission_rates: this.commissionRates(),
        late_cancellation_fee: this.lateCancellationFee(),
      })
      .subscribe({
        next: (res) => {
          this.commissionRates.set(res.settings.commission_rates || {});
          this.lateCancellationFee.set(Number(res.settings.late_cancellation_fee || 0));
          this.commissionSaving.set(false);
          this.commissionSaved.set(true);
        },
        error: (err) => {
          this.commissionSaving.set(false);
          this.commissionError.set(err?.error?.detail || this.language.t('consoleSettings.failedToSaveSettings'));
        },
      });
  }

  ngOnDestroy(): void {
    this.routeSub.unsubscribe();
    if (this.timer) clearTimeout(this.timer);
  }

  load(): void {
    this.isLoading.set(true);
    this.console.getPayments({
      q: this.query(), status: this.status(), page: this.page(), page_size: this.pageSize,
      payout_page: this.payoutPage(), payout_page_size: this.payoutPageSize,
      refund_page: this.refundPage(), refund_page_size: this.refundPageSize,
      refund_status: this.refundStatus(),
    }).subscribe({
      next: (res) => {
        this.payments.set(res.payments);
        this.refunds.set(res.refunds);
        this.refundsTotal.set(res.refunds_total);
        this.refundPage.set(res.refund_page);
        this.payouts.set(res.payouts);
        this.payoutPage.set(res.payout_page);
        this.payoutsTotal.set(res.payouts_total);
        this.payoutTotals.set(res.payout_totals);
        this.total.set(res.total);
        this.page.set(res.page);
        this.revenue.set(res.revenue);
        this.statusCounts.set(res.status_counts);
        this.error.set(null);
        this.isLoading.set(false);
      },
      error: () => this.isLoading.set(false),
    });
  }

  onSearch(value: string): void {
    this.query.set(value);
    this.page.set(1);
    this.payoutPage.set(1);
    this.refundPage.set(1);
    if (this.timer) clearTimeout(this.timer);
    this.timer = setTimeout(() => this.load(), 550);
  }

  onStatusChange(value: string): void {
    this.status.set(value);
    this.page.set(1);
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
    this.refundStatus.set('all');
    this.page.set(1);
    this.payoutPage.set(1);
    this.refundPage.set(1);
    if (this.timer) clearTimeout(this.timer);
    this.load();
  }

  changePage(page: number): void {
    this.page.set(page);
    this.load();
  }

  changePayoutPage(page: number): void {
    this.payoutPage.set(page);
    this.load();
  }

  changeRefundPage(page: number): void {
    this.refundPage.set(page);
    this.load();
  }

  onRefundStatusChange(value: string): void {
    this.refundStatus.set(value);
    this.refundPage.set(1);
    this.load();
  }

  viewPayout(payout: Payout): void {
    this.selectedPayout.set(payout);
  }

  refund(p: Payment): void {
    if (!confirm(`Issue a refund?\n\n${p.reference} — ${usd(p.amount)}`)) return;
    this.console.createRefund({ payment: p.id, reason: 'other' }).subscribe({
      next: () => this.load(),
      error: (err) => {
        const detail = (err as { error?: { detail?: string } }).error?.detail;
        this.error.set(
          detail === 'payment_not_refundable'
            ? 'Only successful payments can be refunded.'
            : detail || 'Failed to issue refund.',
        );
      },
    });
  }

  payPayout(payout: Payout): void {
    const owner = payout.owner;
    const account = [
      this.payoutMethodLabel(owner.payout_method || payout.payout_method),
      owner.payout_account_name || payout.payout_account_name,
      owner.payout_account_number || payout.payout_account_number,
      owner.payout_bank_name || payout.payout_bank_name,
    ]
      .filter(Boolean)
      .join(' · ');
    if (!owner.has_payout_details) {
      this.error.set(
        `The owner has not added payout details yet. Ask them to fill in Profile → Payout account.`
      );
      return;
    }
    const note = window.prompt(
      `Send ${payout.amount_display} to the owner after the ${payout.commission_rate}% ${this.methodLabel(payout.payment_method)} commission.\nGross payment: ${this.usd(payout.gross_amount)}\nCommission: ${this.usd(payout.commission_amount)}\n\n${account}\n\nEnter the transfer reference / note (optional):`,
      'Manual bank transfer'
    );
    if (note === null) return;
    if (
      !confirm(
        `Mark this payout as paid?\n\n${payout.reference} — ${payout.amount_display}\nGross payment: ${this.usd(payout.gross_amount)}\nCommission: ${this.usd(payout.commission_amount)}\nPayment method: ${this.methodLabel(payout.payment_method)}\n${account}\n\nThis does not move money; only record it after the transfer is complete.`
      )
    )
      return;
    this.isSaving.set(true);
    this.console.payPayout(payout.id, note).subscribe({
      next: () => {
        this.isSaving.set(false);
        this.load();
      },
      error: (err) => {
        this.isSaving.set(false);
        const detail = (err as { error?: { detail?: string } }).error?.detail;
        const messages: Record<string, string> = {
          payout_not_due: 'The 7-day hold period has not finished yet.',
          payout_details_missing: 'The owner has not added payout details yet.',
          payout_blocked: 'This payment was cancelled or refunded.',
          payout_already_paid: 'This payout was already recorded as paid.',
        };
        this.setError(err, messages[detail || ''] || 'Failed to record payout.');
      },
    });
  }

  openRefundChat(refund: Refund, party: 'renter' | 'owner'): void {
    this.isSaving.set(true);
    this.error.set(null);
    this.chat.openConsoleRefundChat(refund.id, party).subscribe({
      next: (res) => {
        this.isSaving.set(false);
        void this.router.navigateByUrl(res.url);
      },
      error: (err) => {
        this.isSaving.set(false);
        this.setError(err, 'Failed to open the refund chat.');
      },
    });
  }

  accept(r: Refund): void {
    const cancellationFee = Number(r.commission_due || 0);
    const note = prompt('Admin review note (optional):', '') ?? '';
    let commissionPaid = false;
    if (cancellationFee > 0 && !r.commission_paid) {
      if (
        !confirm(
          `This cancellation is after the 5-day free window. The renter must pay the ${this.usd(cancellationFee)} cancellation fee separately. Confirm payment was received before accepting.`
        )
      )
        return;
      commissionPaid = true;
    }
    if (!confirm(`Accept refund request ${r.reference}? The refund will be approved.`)) return;
    this.isSaving.set(true);
    this.console.acceptRefund(r.id, { note, commission_paid: commissionPaid }).subscribe({
      next: () => {
        this.isSaving.set(false);
        this.load();
      },
      error: (err) => {
        this.isSaving.set(false);
        this.setError(err, 'Failed to accept refund request.');
      },
    });
  }

  markCommissionPaid(r: Refund): void {
    if (!confirm(`Confirm the renter paid the ${this.usd(r.commission_due)} cancellation fee separately?`)) return;
    this.isSaving.set(true);
    this.console.markRefundCommissionPaid(r.id).subscribe({
      next: () => {
        this.isSaving.set(false);
        this.load();
      },
      error: (err) => {
        this.isSaving.set(false);
        this.setError(err, 'Failed to record cancellation fee payment.');
      },
    });
  }

  process(r: Refund, external = false): void {
    const message = external
      ? 'Approve this refund request? First complete the refund in the ABA PayWay merchant portal. This action only records that the money was sent.'
      : 'Approve and process this refund request?';
    if (!confirm(message)) return;
    const note = prompt('Review or processing note (optional):', '') ?? '';
    this.console.processRefund(r.id, { external, note }).subscribe({
      next: () => this.load(),
      error: (err) => this.setError(err, 'Failed to process refund.'),
    });
  }

  reject(r: Refund): void {
    const note = prompt('Explain why the refund request is cancelled. This note will be shared with the renter and owner:', '');
    if (note === null) return;
    if (!note.trim()) {
      this.error.set('Add a review note before cancelling the request.');
      return;
    }
    if (!confirm(`Cancel refund request ${r.reference}?`)) return;
    this.console.rejectRefund(r.id, note.trim()).subscribe({
      next: () => this.load(),
      error: (err) => this.setError(err, 'Failed to reject refund request.'),
    });
  }

  private setError(err: unknown, fallback: string): void {
    const detail = (err as { error?: { detail?: string } }).error?.detail;
    this.error.set(detail || fallback);
  }
}
