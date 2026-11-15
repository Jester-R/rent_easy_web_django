import { Component, computed, inject, OnDestroy, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { IconComponent } from '../../../components/icon/icon';
import { DataPaginationComponent } from '../../../components/data-pagination/data-pagination';
import {
  SearchableSelectComponent,
  SelectOption,
} from '../../../components/searchable-select/searchable-select';
import { ConsoleService } from '../../../services/console.service';
import { LanguageService } from '../../../services/language.service';
import { AuditReportItem, ConsoleAuditResponse, RoleOption } from '../../../models';
import { initials, prettyDate } from '../../../shared/ui';

@Component({
  selector: 'app-console-audit',
  imports: [
    CommonModule,
    FormsModule,
    IconComponent,
    SearchableSelectComponent,
    DataPaginationComponent,
  ],
  templateUrl: './console-audit.html',
})
export class ConsoleAuditComponent implements OnInit, OnDestroy {
  private readonly console = inject(ConsoleService);
  readonly language = inject(LanguageService);

  readonly initials = initials;
  readonly prettyDate = prettyDate;

  readonly logs = signal<AuditReportItem[]>([]);
  readonly total = signal(0);
  readonly page = signal(1);
  readonly pageSize = 25;
  readonly actions = signal<RoleOption[]>([]);
  readonly entities = signal<RoleOption[]>([]);
  readonly byAction = signal<{ action: string; n: number }[]>([]);
  readonly byEntity = signal<{ entity: string; n: number }[]>([]);
  readonly byDay = signal<{ date: string; count: number }[]>([]);
  readonly query = signal('');
  readonly action = signal('all');
  readonly entity = signal('all');
  readonly dateFrom = signal('');
  readonly dateTo = signal('');
  readonly isLoading = signal(true);
  readonly isExporting = signal(false);
  readonly error = signal<string | null>(null);

  private timer: ReturnType<typeof setTimeout> | null = null;

  readonly logins = computed(
    () => this.byAction().find((item) => item.action === 'login')?.n ?? 0
  );
  readonly securityEvents = computed(
    () =>
      this.byAction()
        .filter((item) => item.action === 'login' || item.action === 'logout')
        .reduce((sum, item) => sum + item.n, 0)
  );
  readonly changes = computed(() =>
    this.byAction()
      .filter((item) => !['login', 'logout'].includes(item.action))
      .reduce((sum, item) => sum + item.n, 0)
  );
  readonly maxDaily = computed(() =>
    Math.max(...this.byDay().map((day) => day.count), 1)
  );
  readonly maxAction = computed(() =>
    Math.max(...this.byAction().map((item) => item.n), 1)
  );

  readonly actionOptions = computed<SelectOption[]>(() => [
    { value: 'all', label: this.language.t('consoleAudit.allActions') },
    ...this.actions().map((item) => ({
      value: item.value,
      label: this.language.valueLabel(item.label),
    })),
  ]);

  readonly entityOptions = computed<SelectOption[]>(() => [
    { value: 'all', label: this.language.t('consoleAudit.allEntities') },
    ...this.entities().map((item) => ({
      value: item.value,
      label: item.label,
    })),
  ]);

  ngOnInit(): void {
    this.load();
  }

  ngOnDestroy(): void {
    if (this.timer) clearTimeout(this.timer);
  }

  load(): void {
    this.isLoading.set(true);
    this.console
      .getAuditLogs({
        q: this.query(),
        action: this.action(),
        entity: this.entity(),
        date_from: this.dateFrom(),
        date_to: this.dateTo(),
        page: this.page(),
        page_size: this.pageSize,
      })
      .subscribe({
        next: (res) => {
          this.applyResponse(res);
          this.error.set(null);
          this.isLoading.set(false);
        },
        error: () => {
          this.error.set(this.language.t('consoleAudit.loadFailed'));
          this.isLoading.set(false);
        },
      });
  }

  private applyResponse(res: ConsoleAuditResponse): void {
    this.logs.set(res.logs);
    this.total.set(res.total);
    this.page.set(res.page);
    this.actions.set(res.actions ?? []);
    this.entities.set(res.entities ?? []);
    this.byAction.set(res.by_action ?? []);
    this.byEntity.set(res.by_entity ?? []);
    this.byDay.set(res.by_day ?? []);
  }

  onSearch(value: string): void {
    this.query.set(value);
    this.page.set(1);
    if (this.timer) clearTimeout(this.timer);
    this.timer = setTimeout(() => this.load(), 450);
  }

  onActionChange(value: string): void {
    this.action.set(value);
    this.page.set(1);
    this.load();
  }

  onEntityChange(value: string): void {
    this.entity.set(value);
    this.page.set(1);
    this.load();
  }

  applyFilter(): void {
    if (this.timer) clearTimeout(this.timer);
    this.page.set(1);
    this.load();
  }

  reset(): void {
    if (this.timer) clearTimeout(this.timer);
    this.query.set('');
    this.action.set('all');
    this.entity.set('all');
    this.dateFrom.set('');
    this.dateTo.set('');
    this.page.set(1);
    this.load();
  }

  changePage(page: number): void {
    this.page.set(page);
    this.load();
  }

  exportCsv(): void {
    if (this.isExporting()) return;
    this.isExporting.set(true);
    this.console
      .downloadAuditLogs({
        q: this.query(),
        action: this.action(),
        entity: this.entity(),
        date_from: this.dateFrom(),
        date_to: this.dateTo(),
      })
      .subscribe({
        next: (blob) => {
          this.saveBlob(blob, `audit-log-${new Date().toISOString().slice(0, 10)}.csv`);
          this.isExporting.set(false);
        },
        error: () => {
          this.error.set(this.language.t('consoleAudit.exportFailed'));
          this.isExporting.set(false);
        },
      });
  }

  actionLabel(value: string): string {
    const label = this.actions().find((item) => item.value === value)?.label || value;
    return this.language.valueLabel(label);
  }

  actionPill(value: string): string {
    if (value === 'login') return 'pill-approved';
    if (value === 'logout') return 'pill-neutral';
    if (value === 'delete') return 'pill-rejected';
    if (value === 'status') return 'pill-pending';
    if (['payment', 'payout', 'refund'].includes(value)) return 'pill-refunded';
    return 'pill-neutral';
  }

  entityLabel(value: string): string {
    return value.replace(/_/g, ' ');
  }

  dayLabel(value: string): string {
    const date = new Date(`${value}T00:00:00`);
    if (Number.isNaN(date.getTime())) return value;
    const month = this.language.monthName(date.getMonth());
    return `${String(date.getDate()).padStart(2, '0')} ${month}`;
  }

  dayBarHeight(count: number): number {
    return Math.max(3, (count / this.maxDaily()) * 100);
  }

  actionBarWidth(count: number): number {
    return Math.max(3, (count / this.maxAction()) * 100);
  }

  private saveBlob(blob: Blob, filename: string): void {
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  }
}
