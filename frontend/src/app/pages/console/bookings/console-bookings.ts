import { Component, computed, inject, OnDestroy, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { ConsoleService } from '../../../services/console.service';
import { IconComponent } from '../../../components/icon/icon';
import { Booking } from '../../../models';
import { bookingPill, shortDate, usd } from '../../../shared/ui';

@Component({
  selector: 'app-console-bookings',
  imports: [CommonModule, RouterLink, IconComponent],
  templateUrl: './console-bookings.html',
})
export class ConsoleBookingsComponent implements OnInit, OnDestroy {
  private readonly console = inject(ConsoleService);

  readonly bookingPill = bookingPill;
  readonly shortDate = shortDate;
  readonly usd = usd;

  bookings = signal<Booking[]>([]);
  total = signal(0);
  statusCounts = signal<Record<string, number>>({});
  query = signal('');
  status = signal('all');
  isLoading = signal(true);
  error = signal<string | null>(null);
  selected = signal<number[]>([]);

  private timer: ReturnType<typeof setTimeout> | null = null;

  allSelected = computed(() => {
    const list = this.bookings();
    return list.length > 0 && list.every((b) => this.selected().includes(b.id));
  });

  statusOptions = computed(() => {
    const c = this.statusCounts();
    return [
      { value: 'all', label: `All (${c['all'] ?? 0})` },
      { value: 'Pending', label: `Pending (${c['Pending'] ?? 0})` },
      { value: 'Approved', label: `Approved (${c['Approved'] ?? 0})` },
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
    this.selected.set(this.allSelected() ? [] : this.bookings().map((b) => b.id));
  }

  clearSelection(): void {
    this.selected.set([]);
  }

  remove(b: Booking): void {
    if (!confirm(`Delete this record? This cannot be undone?\n\n${b.reference}`)) return;
    this.console.deleteBooking(b.id).subscribe({
      next: () => this.load(),
      error: (err) => this.setError(err, 'Failed to delete booking.'),
    });
  }

  bulkDelete(): void {
    const ids = this.selected();
    if (!ids.length) return;
    if (!confirm(`Delete this record? This cannot be undone?\n\n${ids.length} records`)) return;
    this.console.bulkDeleteBookings(ids).subscribe({
      next: () => this.load(),
      error: (err) => this.setError(err, 'Failed to delete bookings.'),
    });
  }

  private setError(err: unknown, fallback: string): void {
    const detail = (err as { error?: { detail?: string } }).error?.detail;
    this.error.set(detail || fallback);
  }
}