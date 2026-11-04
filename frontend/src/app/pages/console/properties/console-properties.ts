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
import { ConsolePropertyItem, PropertyCategorySetting, User } from '../../../models';
import { usd } from '../../../shared/ui';
import { PropertyCategoryService } from '../../../services/property-category.service';

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
  private readonly propertyCategoryService = inject(PropertyCategoryService);
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
  categories = signal<PropertyCategorySetting[]>([]);
  showCategoryModal = signal(false);
  categoryQuery = signal('');
  categoryPage = signal(1);
  readonly categoryPageSize = 8;
  editingCategoryIndexes = signal<number[]>([]);
  categoriesSaved = signal(false);
  categoryError = signal<string | null>(null);
  isSavingCategories = signal(false);

  readonly ownerOptions = computed<SelectOption[]>(() => [
    { value: '', label: this.language.t('consoleProperties.allOwners') },
    ...this.owners().map((item) => ({ value: String(item.id), label: item.display_name })),
  ]);
  readonly filteredCategories = computed(() => {
    const query = this.categoryQuery().trim().toLocaleLowerCase();
    return this.categories().filter((item) =>
      !query || `${item.value} ${item.label_en} ${item.label_km}`.toLocaleLowerCase().includes(query),
    );
  });
  readonly categoryPageItems = computed(() => {
    const start = (this.categoryPage() - 1) * this.categoryPageSize;
    return this.filteredCategories().slice(start, start + this.categoryPageSize).map((category) => ({
      category,
      index: this.categories().indexOf(category),
    }));
  });

  ngOnInit(): void {
    this.load();
    this.loadCategories();
  }

  loadCategories(): void {
    this.console.getSettings().subscribe({
      next: (res) => this.categories.set(res.settings.property_categories || []),
      error: () => this.categoryError.set(this.language.t('consoleSettings.failedToLoadSettings')),
    });
  }

  openCategoryModal(): void {
    this.categoryQuery.set('');
    this.categoryPage.set(1);
    this.showCategoryModal.set(true);
  }

  closeCategoryModal(): void {
    if (!this.isSavingCategories()) this.showCategoryModal.set(false);
  }

  addCategory(): void {
    const existing = new Set(this.categories().map((item) => item.value.trim().toLowerCase()));
    const base = `new_category_${Date.now().toString(36)}`;
    let value = base.slice(0, 24);
    let suffix = 1;
    while (existing.has(value)) {
      const tail = `_${suffix++}`;
      value = `${base.slice(0, 24 - tail.length)}${tail}`;
    }
    this.categories.update((items) => {
      const next = [...items, { value, label_en: 'New category', label_km: 'ប្រភេទថ្មី' }];
      this.editingCategoryIndexes.set([next.length - 1]);
      return next;
    });
    this.categoryQuery.set('');
    this.categoryPage.set(Math.ceil(this.categories().length / this.categoryPageSize));
    this.categoryError.set(null);
    this.categoriesSaved.set(false);
  }

  isCategoryEditing(index: number): boolean {
    return this.editingCategoryIndexes().includes(index);
  }

  updateCategory(index: number, field: 'value' | 'label_en' | 'label_km', value: string): void {
    this.categories.update((items) => items.map((item, itemIndex) =>
      itemIndex === index ? { ...item, [field]: value } : item,
    ));
    this.categoriesSaved.set(false);
  }

  toggleCategoryEditing(index: number): void {
    this.editingCategoryIndexes.update((indexes) =>
      indexes.includes(index) ? indexes.filter((item) => item !== index) : [...indexes, index],
    );
  }

  removeCategory(value: string): void {
    this.categories.update((items) => items.filter((item) => item.value !== value));
    this.editingCategoryIndexes.set([]);
    const pageCount = Math.max(1, Math.ceil(this.filteredCategories().length / this.categoryPageSize));
    this.categoryPage.update((page) => Math.min(page, pageCount));
    this.categoryError.set(null);
    this.categoriesSaved.set(false);
  }

  saveCategories(): void {
    const categories = this.categories().map((item) => ({
      ...item,
      value: item.value.trim().toLowerCase().replace(/[^a-z0-9_-]+/g, '_').slice(0, 24),
      label_en: item.label_en.trim(),
      label_km: item.label_km.trim(),
    }));
    const keys = categories.map((item) => item.value);
    if (categories.some((item) => !item.value || !item.label_en || !item.label_km)) {
      this.categoryError.set(this.language.t('consoleSettings.categoryFieldsRequired'));
      return;
    }
    if (new Set(keys).size !== keys.length) {
      this.categoryError.set(this.language.t('consoleSettings.categoryKeysMustBeUnique'));
      return;
    }

    this.categories.set(categories);
    this.isSavingCategories.set(true);
    this.categoryError.set(null);
    this.console.updateSettings({ property_categories: categories }).subscribe({
      next: (res) => {
        this.categories.set(res.settings.property_categories);
        this.propertyCategoryService.setCategories(res.settings.property_categories);
        this.editingCategoryIndexes.set([]);
        this.categoriesSaved.set(true);
        this.isSavingCategories.set(false);
        this.categoryPage.set(Math.min(this.categoryPage(), Math.max(1, Math.ceil(this.filteredCategories().length / this.categoryPageSize))));
      },
      error: (err) => {
        this.isSavingCategories.set(false);
        this.categoryError.set(err?.error?.detail || this.language.t('consoleSettings.failedToSaveSettings'));
      },
    });
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
