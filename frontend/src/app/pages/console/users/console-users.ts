import { Component, computed, inject, OnDestroy, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { IconComponent } from '../../../components/icon/icon';
import { AuthService } from '../../../services/auth.service';
import { ConsoleService } from '../../../services/console.service';
import { LanguageService } from '../../../services/language.service';
import { ConsoleUserItem, RoleOption } from '../../../models';
import { initials, roleLabel, rolePill, shortDate } from '../../../shared/ui';

@Component({
  selector: 'app-console-users',
  imports: [RouterLink, IconComponent],
  templateUrl: './console-users.html',
})
export class ConsoleUsersComponent implements OnInit, OnDestroy {
  private readonly console = inject(ConsoleService);
  readonly auth = inject(AuthService);
  readonly language = inject(LanguageService);

  readonly rolePill = rolePill;
  readonly roleLabel = roleLabel;
  readonly shortDate = shortDate;
  readonly initials = initials;

  users = signal<ConsoleUserItem[]>([]);
  total = signal(0);
  roles = signal<RoleOption[]>([]);
  query = signal('');
  role = signal('all');
  isLoading = signal(true);
  error = signal<string | null>(null);
  selected = signal<number[]>([]);

  private timer: ReturnType<typeof setTimeout> | null = null;

  allSelected = computed(() => {
    const list = this.users();
    return list.length > 0 && list.every((u) => this.selected().includes(u.id));
  });

  hasFilters = computed(() => this.query() !== '' || this.role() !== 'all');

  label(value: string): string {
    const khmer: Record<string, string> = {
      'Super Admin': 'អ្នកគ្រប់គ្រងកំពូល',
      'Property Owner': 'ម្ចាស់អចលនទ្រព្យ',
      Renter: 'អ្នកជួល',
    };
    return this.language.current() === 'km' ? (khmer[value] ?? value) : value;
  }

  ngOnInit(): void {
    this.load();
  }

  ngOnDestroy(): void {
    if (this.timer) clearTimeout(this.timer);
  }

  load(): void {
    this.isLoading.set(true);
    this.console.getUsers({ q: this.query(), role: this.role() }).subscribe({
      next: (res) => {
        this.users.set(res.users);
        this.total.set(res.total);
        this.roles.set(res.roles);
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

  onRoleChange(value: string): void {
    this.role.set(value);
    if (this.timer) clearTimeout(this.timer);
    this.load();
  }

  applyFilter(): void {
    if (this.timer) clearTimeout(this.timer);
    this.load();
  }

  refresh(): void {
    this.query.set('');
    this.role.set('all');
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
    this.selected.set(this.allSelected() ? [] : this.users().map((u) => u.id));
  }

  clearSelection(): void {
    this.selected.set([]);
  }

  remove(item: ConsoleUserItem): void {
    if (!confirm(`Delete this record? This cannot be undone?\n\n${item.email}`)) return;
    this.console.deleteUser(item.id).subscribe({
      next: () => {
        this.clearSelection();
        this.load();
      },
      error: (err) => this.setError(err, 'Failed to delete user.'),
    });
  }

  bulkDelete(): void {
    const ids = this.selected();
    if (!ids.length) return;
    if (!confirm(`Delete this record? This cannot be undone?\n\n${ids.length} selected`)) return;
    this.console.bulkDeleteUsers(ids).subscribe({
      next: () => {
        this.clearSelection();
        this.load();
      },
      error: (err) => this.setError(err, 'Failed to delete users.'),
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
