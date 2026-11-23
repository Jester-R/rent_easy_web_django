import { Component, computed, inject, OnDestroy, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { IconComponent } from '../../../components/icon/icon';
import { DataPaginationComponent } from '../../../components/data-pagination/data-pagination';
import {
  SearchableSelectComponent,
  SelectOption,
} from '../../../components/searchable-select/searchable-select';
import { AuthService } from '../../../services/auth.service';
import { ConsoleService } from '../../../services/console.service';
import { LanguageService } from '../../../services/language.service';
import { ConsoleSessionsResponse, LoginSessionItem, RoleOption } from '../../../models';
import { prettyDate, shortDate } from '../../../shared/ui';

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
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  readonly language = inject(LanguageService);

  readonly prettyDate = prettyDate;
  readonly shortDate = shortDate;

  readonly data = signal<ConsoleSessionsResponse | null>(null);
  readonly sessions = signal<LoginSessionItem[]>([]);
  readonly total = signal(0);
  readonly page = signal(1);
  readonly pageSize = 25;
  readonly activeCount = signal(0);
  readonly inactiveCount = signal(0);
  readonly methods = signal<RoleOption[]>([]);
  readonly query = signal('');
  readonly status = signal('all');
  readonly method = signal('all');
  readonly isLoading = signal(true);
  readonly isExporting = signal(false);
  readonly error = signal<string | null>(null);
  readonly selected = signal<number[]>([]);
  readonly busyIds = signal<number[]>([]);
  readonly isBulkBusy = signal(false);

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

  readonly selectedCount = computed(() => this.selected().length);
  readonly visibleLogoutIds = computed(() =>
    this.sessions()
      .filter((item) => item.is_active)
      .map((item) => item.id)
  );
  readonly allVisibleSelected = computed(() => {
    const ids = this.visibleLogoutIds();
    return ids.length > 0 && ids.every((id) => this.selected().includes(id));
  });
  readonly allVisibleBusy = computed(() => {
    const ids = this.visibleLogoutIds();
    return ids.length > 0 && ids.every((id) => this.busyIds().includes(id));
  });

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
          const visible = new Set(res.sessions.map((item) => item.id));
          this.selected.update((ids) => ids.filter((id) => visible.has(id)));
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

  applyFilter(): void {
    if (this.timer) clearTimeout(this.timer);
    this.load();
  }

  reset(): void {
    if (this.timer) clearTimeout(this.timer);
    this.query.set('');
    this.status.set('all');
    this.method.set('all');
    this.page.set(1);
    this.load();
  }

  changePage(page: number): void {
    this.page.set(page);
    this.load();
  }

  isSelected(id: number): boolean {
    return this.selected().includes(id);
  }

  isBusy(id: number): boolean {
    return this.busyIds().includes(id);
  }

  toggle(id: number): void {
    if (this.isBusy(id)) return;
    const cur = this.selected();
    this.selected.set(cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]);
  }

  toggleAllVisible(): void {
    const ids = this.visibleLogoutIds();
    if (!ids.length || this.allVisibleBusy()) return;
    const cur = new Set(this.selected());
    if (this.allVisibleSelected()) {
      ids.forEach((id) => cur.delete(id));
    } else {
      ids.forEach((id) => cur.add(id));
    }
    this.selected.set([...cur]);
  }

  clearSelection(): void {
    this.selected.set([]);
  }

  logout(session: LoginSessionItem): void {
    if (!session.is_active || this.isBusy(session.id)) return;
    const label = session.is_current
      ? this.language.t('consoleSessions.confirmLogoutCurrent')
      : this.language.t('consoleSessions.confirmLogoutSingle');
    if (!confirm(label)) return;
    this.busyIds.update((ids) => [...ids, session.id]);
    this.console.logoutSession(session.id).subscribe({
      next: (res) => {
        this.selected.update((ids) => ids.filter((id) => id !== session.id));
        this.busyIds.update((ids) => ids.filter((id) => id !== session.id));
        this.afterLogout(res.current ?? session.is_current);
      },
      error: () => {
        this.busyIds.update((ids) => ids.filter((id) => id !== session.id));
        this.error.set(this.language.t('consoleSessions.logoutFailed'));
      },
    });
  }

  bulkLogout(): void {
    const ids = this.selected().filter((id) => !this.busyIds().includes(id));
    if (!ids.length || this.isBulkBusy()) return;
    const message = this.language
      .t('consoleSessions.confirmLogoutMultiple')
      .replace('{count}', String(ids.length));
    if (!confirm(message)) return;
    this.isBulkBusy.set(true);
    this.busyIds.update((busy) => [...new Set([...busy, ...ids])]);
    this.console.bulkLogoutSessions(ids).subscribe({
      next: (res) => {
        this.isBulkBusy.set(false);
        this.selected.set([]);
        this.busyIds.update((busy) => busy.filter((id) => !ids.includes(id)));
        this.afterLogout(res.current_logged_out ?? false);
      },
      error: () => {
        this.isBulkBusy.set(false);
        this.busyIds.update((busy) => busy.filter((id) => !ids.includes(id)));
        this.error.set(this.language.t('consoleSessions.logoutFailed'));
      },
    });
  }

  exportCsv(): void {
    if (this.isExporting()) return;
    this.isExporting.set(true);
    this.console
      .downloadSessions({
        q: this.query(),
        status: this.status(),
        method: this.method(),
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

  private afterLogout(currentLoggedOut: boolean): void {
    if (!currentLoggedOut) {
      this.load();
      return;
    }
    this.auth.currentUser.set(null);
    void this.router.navigate(['/login']);
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
