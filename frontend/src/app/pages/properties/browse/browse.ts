import { Component, computed, inject, OnInit, PLATFORM_ID, signal } from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { PropertyService, PropertyBrowseResponse } from '../../../services/property.service';
import { Property } from '../../../models';
import { PropertyCardComponent } from '../../../components/property-card/property-card';
import { LanguageService } from '../../../services/language.service';
import { PROPERTY_CATEGORIES } from '../../../shared/ui';
import {
  SearchableSelectComponent,
  SelectOption,
} from '../../../components/searchable-select/searchable-select';

@Component({
  selector: 'app-browse-properties',
  imports: [CommonModule, FormsModule, PropertyCardComponent, SearchableSelectComponent],
  templateUrl: './browse.html',
})
export class BrowsePropertiesComponent implements OnInit {
  readonly language = inject(LanguageService);
  private readonly propertyService = inject(PropertyService);
  private readonly platformId = inject(PLATFORM_ID);

  properties = signal<Property[]>([]);
  locations = signal<string[]>([]);
  isLoading = signal(true);
  loadError = signal(false);

  readonly categories = PROPERTY_CATEGORIES;

  // Filters
  searchTerm = '';
  selectedLocation = '__all__';
  selectedCategory = '__all__';
  minBedrooms = 0;
  maxPrice: number | undefined;
  sort = 'recommended';

  readonly locationOptions = computed<SelectOption[]>(() => [
    { value: '__all__', label: this.language.t('All Locations', 'គ្រប់ទីតាំង') },
    ...this.locations().map((loc) => ({ value: loc, label: loc })),
  ]);

  readonly categoryOptions: SelectOption[] = [
    { value: '__all__', label: this.language.t('All Categories', 'គ្រប់ប្រភេទ') },
    ...this.categories.map((cat) => ({ value: cat.value, label: cat.label })),
  ];

  readonly bedroomOptions: SelectOption[] = [
    { value: '0', label: this.language.t('Any', 'ទាំងអស់') },
    { value: '1', label: '1+' },
    { value: '2', label: '2+' },
    { value: '3', label: '3+' },
    { value: '4', label: '4+' },
  ];

  readonly sortOptions: SelectOption[] = [
    { value: 'recommended', label: this.language.t('Recommended', 'ណែនាំ') },
    { value: 'price_low', label: this.language.t('Price: Low to High', 'តម្លៃ៖ ទាបទៅខ្ពស់') },
    { value: 'price_high', label: this.language.t('Price: High to Low', 'តម្លៃ៖ ខ្ពស់ទៅទាប') },
    { value: 'bedrooms', label: this.language.t('Most Bedrooms', 'បន្ទប់គេងច្រើនបំផុត') },
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
      })
      .subscribe({
        next: (res: PropertyBrowseResponse) => {
          this.properties.set(res.properties);
          this.locations.set(res.meta.locations);
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
    this.loadProperties();
  }

  resetFilters(): void {
    this.searchTerm = '';
    this.selectedLocation = '__all__';
    this.selectedCategory = '__all__';
    this.minBedrooms = 0;
    this.maxPrice = undefined;
    this.sort = 'recommended';
    this.loadProperties();
  }
}
