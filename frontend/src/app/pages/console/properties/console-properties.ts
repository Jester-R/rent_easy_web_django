import { Component, computed, inject, OnDestroy, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { IconComponent } from '../../../components/icon/icon';
import { ConsoleService } from '../../../services/console.service';
import { ConsolePropertyItem, User } from '../../../models';
import { usd } from '../../../shared/ui';

@Component({
  selector: 'app-console-properties',
  imports: [RouterLink, IconComponent],
  templateUrl: './console-properties.html',
})
export class ConsolePropertiesComponent implements OnInit, OnDestroy {
  private readonly console = inject(ConsoleService);

  readonly usd = usd;

  properties = signal<ConsolePropertyItem[]>([]);
  total = signal(0);
  owners = signal<User[]>([]);
  query = signal('');
  owner = signal('');
  isLoading = signal(true);
  error = signal<string | null>(null);
  selected = signal<number[]>([]);

  private timer: ReturnType<typeof setTimeout> | null = null;

  allSelected = computed(() => {
    const list = this.properties();
    return list.length > 0 && list.every((p) => this.selected().includes(p.id));
  });

  hasFilters = computed(() => this.query() !== '' || this.owner() !== '');

  ngOnInit(): void {
    this.load();
  }

  ngOnDestroy(): void {
    if (this.timer) clearTimeout(this.timer);
  }

  load(): void {
    this.isLoading.set(true);
    this.console.getProperties({ q: this.query(), owner: this.owner() }).subscribe({
      next: (res) => {
        this.properties.set(res.properties);
        this.total.set(res.total);
        this.owners.set(res.owners);
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

  onOwnerChange(value: string): void {
    this.owner.set(value);
    if (this.timer) clearTimeout(this.timer);
    this.load();
  }

  applyFilter(): void {
    if (this.timer) clearTimeout(this.timer);
    this.load();
  }

  refresh(): void {
    this.query.set('');
    this.owner.set('');
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
    this.selected.set(this.allSelected() ? [] : this.properties().map((p) => p.id));
  }

  clearSelection(): void {
    this.selected.set([]);
  }

  remove(item: ConsolePropertyItem): void {
    if (!confirm(`Delete this record? This cannot be undone.\n\n${item.title}`)) return;
    this.console.deleteProperty(item.id).subscribe({
      next: () => {
        this.clearSelection();
        this.load();
      },
      error: (err) => this.setError(err, 'Failed to delete property.'),
    });
  }

  bulkDelete(): void {
    const ids = this.selected();
    if (!ids.length) return;
    if (!confirm(`Delete this record? This cannot be undone.\n\n${ids.length} selected`)) return;
    this.console.bulkDeleteProperties(ids).subscribe({
      next: () => {
        this.clearSelection();
        this.load();
      },
      error: (err) => this.setError(err, 'Failed to delete properties.'),
    });
  }

  private setError(err: unknown, fallback: string): void {
    this.error.set(this.friendlyError(err, fallback));
  }

  private friendlyError(err: unknown, fallback: string): string {
    const detail = (err as { error?: { detail?: string } }).error?.detail;
    if (!detail) return fallback;
    const messages: Record<string, string> = {
      email_taken: 'Email or username already in use',
      password_too_short: 'Password must be at least 6 characters.',
      username_invalid: 'Username must be 3-30 characters using letters, numbers, ., _ or -',
      title_required: 'Title is required',
      location_required: 'Location is required',
      price_required: 'Enter a valid price',
      owner_required: 'Select an owner with the Property Owner role.',
    };
    return messages[detail] || detail;
  }
}