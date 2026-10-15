import { Component, computed, inject, OnInit, PLATFORM_ID, signal } from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { PropertyService, PropertyBrowseResponse } from '../../../services/property.service';
import { Property } from '../../../models';
import { PropertyCardComponent } from '../../../components/property-card/property-card';
import { DataPaginationComponent } from '../../../components/data-pagination/data-pagination';
import { LanguageService } from '../../../services/language.service';
import { PropertyCategorySetting } from '../../../models';
import {
  SearchableSelectComponent,
  SelectOption,
} from '../../../components/searchable-select/searchable-select';

@Component({
  selector: 'app-browse-properties',
  imports: [CommonModule, FormsModule, PropertyCardComponent, SearchableSelectComponent, DataPaginationComponent],
  templateUrl: './browse.html',
})
export class BrowsePropertiesComponent implements OnInit {
  readonly language = inject(LanguageService);
  private readonly propertyService = inject(PropertyService);
  private readonly platformId = inject(PLATFORM_ID);

  properties = signal<Property[]>([]);
  total = signal(0);
  page = signal(1);
  readonly pageSize = 24;
  locations = signal<string[]>([]);
  isLoading = signal(true);
  loadError = signal(false);

  categories = signal<PropertyCategorySetting[]>([]);

  // Filters
  searchTerm = '';
  selectedLocation = '__all__';
  selectedCategory = '__all__';
  minBedrooms = 0;
  maxPrice: number | undefined;
  sort = 'recommended';

  readonly locationOptions = computed<SelectOption[]>(() => [
    { value: '__all__', label: this.language.t('browse.allLocations') },
    ...this.locations().map((loc) => ({ value: loc, label: loc })),
  ]);

  readonly categoryOptions = computed<SelectOption[]>(() => [
    { value: '__all__', label: this.language.t('browse.allCategories') },
    ...this.categories().map((cat) => ({
      value: cat.value,
      label: this.language.current() === 'km' ? cat.label_km : cat.label_en,
    })),
  ]);

  readonly bedroomOptions: SelectOption[] = [
    { value: '0', label: this.language.t('browse.any') },
    { value: '1', label: '1+' },
    { value: '2', label: '2+' },
    { value: '3', label: '3+' },
    { value: '4', label: '4+' },
  ];

  readonly sortOptions: SelectOption[] = [
    { value: 'recommended', label: this.language.t('browse.recommended') },
    { value: 'price_low', label: this.language.t('browse.priceLowToHigh') },
    { value: 'price_high', label: this.language.t('browse.priceHighToLow') },
    { value: 'bedrooms', label: this.language.t('browse.mostBedrooms') },
  ];

  ngOnInit(): void {
    // API calls from SSR can loop back into the Angular development server.
    // Load the public listings after hydration, from the browser instead.
    if (isPlatformBrowser(this.platformId)) {
      this.loadProperties();
    }
  }

  loadProperties(): void {
    this.isLoading.set(true);
    this.loadError.set(false);
    this.propertyService
      .browse({
        q: this.searchTerm,
        location: this.selectedLocation,
        category: this.selectedCategory,
        min_bedrooms: this.minBedrooms,
        max_price: this.maxPrice,
        sort: this.sort,
        page: this.page(),
        page_size: this.pageSize,
      })
      .subscribe({
        next: (res: PropertyBrowseResponse) => {
          this.properties.set(res.properties);
          this.total.set(res.meta.total);
          this.page.set(res.meta.page);
          this.locations.set(res.meta.locations);
          this.categories.set(res.meta.categories || []);
          this.isLoading.set(false);
        },
        error: () => {
          this.properties.set([]);
          this.loadError.set(true);
          this.isLoading.set(false);
        },
      });
  }

  onFilterChange(): void {
    this.page.set(1);
    this.loadProperties();
  }

  changePage(page: number): void {
    this.page.set(page);
    this.loadProperties();
  }

  resetFilters(): void {
    this.searchTerm = '';
    this.selectedLocation = '__all__';
    this.selectedCategory = '__all__';
    this.minBedrooms = 0;
    this.maxPrice = undefined;
    this.sort = 'recommended';
    this.page.set(1);
    this.loadProperties();
  }
}
