import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { IconComponent } from '../../../components/icon/icon';
import {
  SearchableSelectComponent,
  SelectOption,
} from '../../../components/searchable-select/searchable-select';
import { ConsoleService } from '../../../services/console.service';
import { LanguageService } from '../../../services/language.service';
import { ConsolePropertyItem, User } from '../../../models';
import { usd } from '../../../shared/ui';

@Component({
  selector: 'app-console-properties',
  imports: [RouterLink, IconComponent, FormsModule, SearchableSelectComponent],
  templateUrl: './console-properties.html',
})
export class ConsolePropertiesComponent implements OnInit {
  readonly language = inject(LanguageService);
  private readonly console = inject(ConsoleService);
  readonly usd = usd;

  properties = signal<ConsolePropertyItem[]>([]);
  owners = signal<User[]>([]);
  total = signal(0);
  query = signal('');
  owner = signal('');
  isLoading = signal(true);
  error = signal<string | null>(null);

  readonly ownerOptions = computed<SelectOption[]>(() => [
    { value: '', label: this.language.t('All owners', 'ម្ចាស់ទាំងអស់') },
    ...this.owners().map((item) => ({ value: String(item.id), label: item.display_name })),
  ]);

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.isLoading.set(true);
    this.console.getProperties({ q: this.query(), owner: this.owner() }).subscribe({
      next: (res) => {
        this.properties.set(res.properties);
        this.owners.set(res.owners);
        this.total.set(res.total);
        this.error.set(null);
        this.isLoading.set(false);
      },
      error: () => {
        this.error.set(this.language.t('Could not load properties.', 'មិនអាចផ្ទុកបញ្ជីអចលនទ្រព្យបានទេ។'));
        this.isLoading.set(false);
      },
    });
  }

  remove(item: ConsolePropertyItem): void {
    if (!item.is_active || !confirm(this.language.t(
      `Remove “${item.title}” from renter browsing? The record will be retained.`,
      `តើលាក់ “${item.title}” ពីអ្នកជួលមែនទេ? ទិន្នន័យនឹងនៅតែរក្សាទុក។`
    ))) return;

    this.console.softDeleteProperty(item.id).subscribe({
      next: () => this.load(),
      error: () => this.error.set(this.language.t('Could not remove this listing.', 'មិនអាចលាក់ការចុះផ្សាយនេះបានទេ។')),
    });
  }
}
