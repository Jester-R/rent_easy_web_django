import { Component, inject, OnInit, PLATFORM_ID, signal } from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { PropertyService, PropertyBrowseResponse } from '../../../services/property.service';
import { Property } from '../../../models';
import { PropertyCardComponent } from '../../../components/property-card/property-card';
import { LanguageService } from '../../../services/language.service';

@Component({
  selector: 'app-browse-properties',
  imports: [CommonModule, FormsModule, PropertyCardComponent],
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

  // Filters
  searchTerm = '';
  selectedLocation = '__all__';
  minBedrooms = 0;
  maxPrice: number | undefined;
  sort = 'recommended';

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
    this.minBedrooms = 0;
    this.maxPrice = undefined;
    this.sort = 'recommended';
    this.loadProperties();
  }
}
