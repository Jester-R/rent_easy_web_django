import { Component, computed, inject, OnDestroy, OnInit, signal } from '@angular/core';
import { ConsoleService } from '../../../services/console.service';
import { LanguageService } from '../../../services/language.service';
import { IconComponent } from '../../../components/icon/icon';
import { Booking } from '../../../models';
import { bookingPill, shortDate, usd } from '../../../shared/ui';

@Component({
  selector: 'app-console-bookings',
  imports: [IconComponent],
  templateUrl: './console-bookings.html',
})
export class ConsoleBookingsComponent implements OnInit, OnDestroy {
  readonly language = inject(LanguageService);
  private readonly console = inject(ConsoleService);

  readonly bookingPill = bookingPill;
  readonly shortDate = shortDate;
  readonly usd = usd;

  label(value: string): string {
    const khmer: Record<string, string> = {
      All: 'ទាំងអស់',
      all: 'ទាំងអស់',
      Pending: 'កំពុងរង់ចាំ', Approved: 'បានអនុម័ត', Confirmed: 'បានបញ្ជាក់',
      Rejected: 'បានបដិសេធ', Cancelled: 'បានលុបចោល',
    };
    return this.language.current() === 'km' ? (khmer[value] ?? value) : value;
  }

  formatStatusOption(value: string, label: string): string {
    const count = label.match(/\((\d+)\)$/)?.[1] ?? '';
    const base = value === 'all' ? 'All' : value;
    return `${this.label(base)} (${count})`;
  }

  bookings = signal<Booking[]>([]);
  total = signal(0);
  statusCounts = signal<Record<string, number>>({});
  query = signal('');
  status = signal('all');
  isLoading = signal(true);
  error = signal<string | null>(null);
  private timer: ReturnType<typeof setTimeout> | null = null;

  statusOptions = computed(() => {
    const c = this.statusCounts();
    return [
      { value: 'all', label: `All (${c['all'] ?? 0})` },
      { value: 'Pending', label: `Pending (${c['Pending'] ?? 0})` },
      { value: 'Approved', label: `Approved (${c['Approved'] ?? 0})` },
      { value: 'Confirmed', label: `Confirmed (${c['Confirmed'] ?? 0})` },
      { value: 'Rejected', label: `Rejected (${c['Rejected'] ?? 0})` },
      { value: 'Cancelled', label: `Cancelled (${c['Cancelled'] ?? 0})` },
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
    this.console.getBookings({ q: this.query(), status: this.status() }).subscribe({
      next: (res) => {
        this.bookings.set(res.bookings);
        this.total.set(res.total);
        this.statusCounts.set(res.status_counts);
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

}
