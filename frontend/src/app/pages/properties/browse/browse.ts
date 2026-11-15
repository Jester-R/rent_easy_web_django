import { Component, computed, inject, OnInit, PLATFORM_ID, signal } from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { FormsModule } from '@angular/forms';
import {
  CambodiaCommune,
  CambodiaDistrict,
  CambodiaProvince,
  CambodiaVillage,
  PropertyService,
  PropertyBrowseResponse,
} from '../../../services/property.service';
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
  isLoading = signal(true);
  loadError = signal(false);
  locationLoadError = signal(false);
  villagesLoading = signal(false);

  categories = signal<PropertyCategorySetting[]>([]);

  private readonly cambodiaProvinces = signal<CambodiaProvince[]>([]);
  private readonly cambodiaDistricts = signal<CambodiaDistrict[]>([]);
  private readonly cambodiaCommunes = signal<CambodiaCommune[]>([]);
  private readonly cambodiaVillages = signal<CambodiaVillage[]>([]);
  private villagesRequested = false;

  // Filters
  searchTerm = '';
  selectedProvince = signal('__all__');
  selectedLocation = signal('__all__');
  selectedCommune = signal('__all__');
  selectedVillage = signal('__all__');
  selectedCategory = '__all__';
  minBedrooms = 0;
  maxPrice: number | undefined;
  sort = 'recommended';

  readonly provinceOptions = computed<SelectOption[]>(() => [
    { value: '__all__', label: this.language.t('browse.allProvinces') },
    ...this.cambodiaProvinces().map((province) => ({
      value: province.code,
      label: this.locationLabel(province.name_en, province.name_km),
    })),
  ]);

  readonly locationOptions = computed<SelectOption[]>(() => {
    if (this.selectedProvince() === '__all__') return [];
    return [
      { value: '__all__', label: this.language.t('browse.allLocations') },
      ...this.cambodiaDistricts()
        .filter((district) => district.province_code === this.selectedProvince())
        .map((district) => ({
          value: district.code,
          label: this.locationLabel(district.name_en, district.name_km),
        })),
    ];
  });

  readonly communeOptions = computed<SelectOption[]>(() => {
    if (this.selectedLocation() === '__all__') return [];
    return [
      { value: '__all__', label: this.language.t('browse.allCommunes') },
      ...this.cambodiaCommunes()
        .filter((commune) => commune.district_code === this.selectedLocation())
        .map((commune) => ({
          value: commune.code,
          label: this.locationLabel(commune.name_en, commune.name_km),
        })),
    ];
  });

  readonly villageOptions = computed<SelectOption[]>(() => {
    if (this.selectedCommune() === '__all__') return [];
    return [
      { value: '__all__', label: this.language.t('browse.allVillages') },
      ...this.cambodiaVillages()
        .filter((village) => village.commune_code === this.selectedCommune())
        .map((village) => ({
          value: village.code,
          label: this.locationLabel(village.name_en, village.name_km),
        })),
    ];
  });

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
      this.loadLocationData();
      this.loadProperties();
    }
  }

  private loadLocationData(): void {
    this.locationLoadError.set(false);
    this.propertyService.getCambodiaProvinces().subscribe({
      next: (provinces) => this.cambodiaProvinces.set(provinces),
      error: () => this.locationLoadError.set(true),
    });
    this.propertyService.getCambodiaDistricts().subscribe({
      next: (districts) => this.cambodiaDistricts.set(districts),
      error: () => this.locationLoadError.set(true),
    });
    this.propertyService.getCambodiaCommunes().subscribe({
      next: (communes) => this.cambodiaCommunes.set(communes),
      error: () => this.locationLoadError.set(true),
    });
  }

  private ensureVillagesLoaded(): void {
    if (this.villagesRequested) return;
    this.villagesRequested = true;
    this.villagesLoading.set(true);
    this.propertyService.getCambodiaVillages().subscribe({
      next: (villages) => {
        this.cambodiaVillages.set(villages);
        this.villagesLoading.set(false);
      },
      error: () => {
        this.villagesRequested = false;
        this.villagesLoading.set(false);
        this.locationLoadError.set(true);
      },
    });
  }

  private locationLabel(nameEn: string, nameKm: string): string {
    return nameEn && nameKm ? `${nameEn} / ${nameKm}` : nameEn || nameKm;
  }

  private provinceFilter(): string {
    const province = this.cambodiaProvinces().find(
      (item) => item.code === this.selectedProvince(),
    );
    return province?.name_en || '__all__';
  }

  private locationFilter(): string {
    const district = this.cambodiaDistricts().find(
      (item) => item.code === this.selectedLocation(),
    );
    return district ? this.locationLabel(district.name_en, district.name_km) : '__all__';
  }

  private communeFilter(): string {
    const commune = this.cambodiaCommunes().find(
      (item) => item.code === this.selectedCommune(),
    );
    return commune?.name_en || '__all__';
  }

  private villageFilter(): string {
    const village = this.cambodiaVillages().find(
      (item) => item.code === this.selectedVillage(),
    );
    return village?.name_en || '__all__';
  }

  loadProperties(): void {
    this.isLoading.set(true);
    this.loadError.set(false);
    this.propertyService
      .browse({
        q: this.searchTerm,
        province: this.provinceFilter(),
        location: this.locationFilter(),
        commune: this.communeFilter(),
        village: this.villageFilter(),
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

  onProvinceChange(code: string): void {
    this.selectedProvince.set(code);
    this.selectedLocation.set('__all__');
    this.selectedCommune.set('__all__');
    this.selectedVillage.set('__all__');
    this.onFilterChange();
  }

  onDistrictChange(code: string): void {
    this.selectedLocation.set(code);
    this.selectedCommune.set('__all__');
    this.selectedVillage.set('__all__');
    this.onFilterChange();
  }

  onCommuneChange(code: string): void {
    this.selectedCommune.set(code);
    this.selectedVillage.set('__all__');
    if (code !== '__all__') this.ensureVillagesLoaded();
    this.onFilterChange();
  }

  onVillageChange(code: string): void {
    this.selectedVillage.set(code);
    this.onFilterChange();
  }

  changePage(page: number): void {
    this.page.set(page);
    this.loadProperties();
  }

  resetFilters(): void {
    this.searchTerm = '';
    this.selectedProvince.set('__all__');
    this.selectedLocation.set('__all__');
    this.selectedCommune.set('__all__');
    this.selectedVillage.set('__all__');
    this.selectedCategory = '__all__';
    this.minBedrooms = 0;
    this.maxPrice = undefined;
    this.sort = 'recommended';
    this.page.set(1);
    this.loadProperties();
  }
}
