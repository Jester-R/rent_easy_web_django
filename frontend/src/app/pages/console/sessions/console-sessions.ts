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
import { ConsoleSessionsResponse, LoginSessionItem, RoleOption } from '../../../models';
import { initials, prettyDate, roleLabel, shortDate } from '../../../shared/ui';

@Component({
  selector: 'app-console-sessions',
  imports: [
    CommonModule,
    FormsModule,
    IconComponent,
    SearchableSelectComponent,
    DataPaginationComponent,
  ],
  templateUrl: './console-sessions.html',
})
export class ConsoleSessionsComponent implements OnInit, OnDestroy {
  private readonly console = inject(ConsoleService);
  readonly language = inject(LanguageService);

  readonly initials = initials;
  readonly prettyDate = prettyDate;
  readonly shortDate = shortDate;
  readonly roleLabel = roleLabel;

  readonly data = signal<ConsoleSessionsResponse | null>(null);
  readonly sessions = signal<LoginSessionItem[]>([]);
  readonly total = signal(0);
  readonly page = signal(1);
  readonly pageSize = 25;
  readonly activeCount = signal(0);
  readonly inactiveCount = signal(0);
  readonly methods = signal<RoleOption[]>([]);
  readonly roles = signal<RoleOption[]>([]);
  readonly query = signal('');
  readonly status = signal('all');
  readonly method = signal('all');
  readonly role = signal('all');
  readonly isLoading = signal(true);
  readonly isExporting = signal(false);
  readonly error = signal<string | null>(null);

  private timer: ReturnType<typeof setTimeout> | null = null;

  readonly allCount = computed(() => this.activeCount() + this.inactiveCount());

  readonly statusOptions = computed<SelectOption[]>(() => [
    { value: 'all', label: `${this.language.t('consoleSessions.allSessions')} (${this.allCount()})` },
    { value: 'active', label: `${this.language.t('consoleSessions.active')} (${this.activeCount()})` },
    { value: 'inactive', label: `${this.language.t('consoleSessions.inactive')} (${this.inactiveCount()})` },
  ]);

  readonly methodOptions = computed<SelectOption[]>(() => [
    { value: 'all', label: this.language.t('consoleSessions.allMethods') },
    ...this.methods().map((item) => ({
      value: item.value,
      label: this.language.valueLabel(item.label),
    })),
  ]);

  readonly roleOptions = computed<SelectOption[]>(() => [
    { value: 'all', label: this.language.t('consoleSessions.allRoles') },
    ...this.roles().map((item) => ({
      value: item.value,
      label: this.language.valueLabel(item.label),
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
      .getSessions({
        q: this.query(),
        status: this.status(),
        method: this.method(),
        role: this.role(),
        page: this.page(),
        page_size: this.pageSize,
      })
      .subscribe({
        next: (res) => {
          this.data.set(res);
          this.sessions.set(res.sessions);
          this.total.set(res.total);
          this.page.set(res.page);
          this.activeCount.set(res.active_count);
          this.inactiveCount.set(res.inactive_count);
          this.methods.set(res.methods ?? []);
          this.roles.set(res.roles ?? []);
          this.error.set(null);
          this.isLoading.set(false);
        },
        error: () => {
          this.error.set(this.language.t('consoleSessions.loadFailed'));
          this.isLoading.set(false);
        },
      });
  }

  onSearch(value: string): void {
    this.query.set(value);
    this.page.set(1);
    if (this.timer) clearTimeout(this.timer);
    this.timer = setTimeout(() => this.load(), 450);
  }

  onStatusChange(value: string): void {
    this.status.set(value);
    this.page.set(1);
    this.load();
  }

  onMethodChange(value: string): void {
    this.method.set(value);
    this.page.set(1);
    this.load();
  }

  onRoleChange(value: string): void {
    this.role.set(value);
    this.page.set(1);
    this.load();
  }

  applyFilter(): void {
    if (this.timer) clearTimeout(this.timer);
    this.load();
  }

  reset(): void {
    if (this.timer) clearTimeout(this.timer);
    this.query.set('');
    this.status.set('all');
    this.method.set('all');
    this.role.set('all');
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
      .downloadSessions({
        q: this.query(),
        status: this.status(),
        method: this.method(),
        role: this.role(),
      })
      .subscribe({
        next: (blob) => {
          this.saveBlob(blob, `login-sessions-${new Date().toISOString().slice(0, 10)}.csv`);
          this.isExporting.set(false);
        },
        error: () => {
          this.error.set(this.language.t('consoleSessions.exportFailed'));
          this.isExporting.set(false);
        },
      });
  }

  deviceLabel(value: string): string {
    if (!value) return this.language.t('consoleSessions.unknown');
    const label = value.charAt(0).toUpperCase() + value.slice(1);
    return this.language.valueLabel(label);
  }

  methodLabel(value: string): string {
    if (!value) return this.language.t('consoleSessions.unknown');
    return this.language.valueLabel(value.charAt(0).toUpperCase() + value.slice(1));
  }

  location(item: LoginSessionItem): string {
    return item.location || this.language.t('consoleSessions.unknown');
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
