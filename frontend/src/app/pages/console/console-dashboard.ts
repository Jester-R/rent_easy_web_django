import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { IconComponent } from '../../components/icon/icon';
import { ConsoleService } from '../../services/console.service';
import { ConsoleDashboardData } from '../../models';
import {
  bookingPill,
  initials,
  prettyDate,
  roleLabel,
  rolePill,
  usd,
} from '../../shared/ui';

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

@Component({
  selector: 'app-console-dashboard',
  imports: [CommonModule, RouterLink, IconComponent],
  templateUrl: './console-dashboard.html',
})
export class ConsoleDashboardComponent implements OnInit {
  private readonly consoleService = inject(ConsoleService);

  readonly usd = usd;
  readonly prettyDate = prettyDate;
  readonly initials = initials;
  readonly roleLabel = roleLabel;
  readonly rolePill = rolePill;
  readonly bookingPill = bookingPill;

  readonly data = signal<ConsoleDashboardData | null>(null);
  readonly isLoading = signal(true);

  readonly funnel = [
    { label: 'Pending', cls: 'bg-warning' },
    { label: 'Approved', cls: 'bg-primary' },
    { label: 'Rejected', cls: 'bg-danger' },
    { label: 'Cancelled', cls: 'bg-ink-3' },
  ];

  ngOnInit(): void {
    this.consoleService.getDashboard().subscribe({
      next: (res) => {
        this.data.set(res);
        this.isLoading.set(false);
      },
      error: () => this.isLoading.set(false),
    });
  }

  barWidth(d: ConsoleDashboardData, status: string): number {
    const total = d.stats.bookings || 1;
    return ((d.status_counts[status] ?? 0) / total) * 100;
  }

  maxTotal(d: ConsoleDashboardData): number {
    return Math.max(...d.monthly_rows.map((r) => r.total), 1);
  }

  monthLabel(iso: string | null): string {
    if (!iso) return '';
    const parts = iso.split('-').map((p) => Number(p));
    if (parts.length < 2 || Number.isNaN(parts[1])) return '';
    return `${MONTHS[(parts[1] - 1) % 12] || ''} ${String(parts[0]).slice(-2)}`;
  }

  auditPill(action: string): string {
    if (action === 'create') return 'pill pill-approved';
    if (action === 'delete') return 'pill pill-rejected';
    return 'pill pill-neutral';
  }
}