import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { IconComponent } from '../../../components/icon/icon';
import { DataPaginationComponent } from '../../../components/data-pagination/data-pagination';
import {
  SearchableSelectComponent,
  SelectOption,
} from '../../../components/searchable-select/searchable-select';
import { ConsoleService } from '../../../services/console.service';
import { LanguageService } from '../../../services/language.service';
import { propertyLocation, propertyTitle } from '../../../shared/property-text';
import type { Property } from '../../../models';
import { ConsolePropertyItem, User } from '../../../models';
import { usd } from '../../../shared/ui';

@Component({
  selector: 'app-console-properties',
  imports: [RouterLink, IconComponent, FormsModule, SearchableSelectComponent, DataPaginationComponent],
  templateUrl: './console-properties.html',
})
export class ConsolePropertiesComponent implements OnInit {
  readonly language = inject(LanguageService);

  title(property: Property): string {
    return propertyTitle(property, this.language.current());
  }

  location(property: Property): string {
    return propertyLocation(property, this.language.current());
  }
  private readonly console = inject(ConsoleService);
  readonly usd = usd;

  properties = signal<ConsolePropertyItem[]>([]);
  owners = signal<User[]>([]);
  total = signal(0);
  page = signal(1);
  readonly pageSize = 25;
  query = signal('');
  owner = signal('');
  isLoading = signal(true);
  error = signal<string | null>(null);

  readonly ownerOptions = computed<SelectOption[]>(() => [
    { value: '', label: this.language.t('consoleProperties.allOwners') },
    ...this.owners().map((item) => ({ value: String(item.id), label: item.display_name })),
  ]);

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.isLoading.set(true);
    this.console.getProperties({ q: this.query(), owner: this.owner(), page: this.page(), page_size: this.pageSize }).subscribe({
      next: (res) => {
        this.properties.set(res.properties);
        this.owners.set(res.owners);
        this.total.set(res.total);
        this.page.set(res.page);
        this.error.set(null);
        this.isLoading.set(false);
      },
      error: () => {
        this.error.set(this.language.t('consoleProperties.couldNotLoadProperties'));
        this.isLoading.set(false);
      },
    });
  }

  changePage(page: number): void {
    this.page.set(page);
    this.load();
  }

  remove(item: ConsolePropertyItem): void {
    if (!item.is_active || !confirm(this.language.t('consoleProperties.removeFromBrowsing', { title: item.title }))) return;

    this.console.softDeleteProperty(item.id).subscribe({
      next: () => this.load(),
      error: () => this.error.set(this.language.t('consoleProperties.couldNotRemoveThisListing')),
    });
  }
}
