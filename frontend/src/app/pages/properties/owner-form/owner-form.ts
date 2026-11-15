import { Component, computed, inject, input, OnInit, PLATFORM_ID, signal } from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { FormBuilder, FormsModule, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import {
  CambodiaCommune,
  CambodiaDistrict,
  CambodiaProvince,
  CambodiaVillage,
  PropertyService,
} from '../../../services/property.service';
import { LanguageService } from '../../../services/language.service';
import { LeafletMapComponent } from '../../../components/leaflet-map/leaflet-map';
import {
  SearchableSelectComponent,
  SelectOption,
} from '../../../components/searchable-select/searchable-select';
import { Property, PropertyCategorySetting } from '../../../models';
import { formatCoordinates, parseCoordinates } from '../../../shared/coords';
import { compressImageToFile } from '../../../shared/image';

const ADMIN_NAME_PREFIX =
  /^(?:province|khaet|khet|city|municipality|district|khan|srok|krong|commune|sangkat|khum|village|phum|phoum|quarter|group|ខេត្ត|រាជធានី|ក្រុង|ខណ្ឌ|ស្រុក|ឃុំ|សង្កាត់|ភូមិ)\s*/iu;
const ADMIN_NAME_SUFFIX =
  /\s+(?:province|municipality|city|district|commune|village)$/iu;

const KHMER_DIGITS: Record<string, string> = {
  '០': '0', '១': '1', '២': '2', '៣': '3', '៤': '4',
  '៥': '5', '៦': '6', '៧': '7', '៨': '8', '៩': '9',
};

const NUMBER_MAPPINGS: { re: RegExp; num: string }[] = [
  // 20-29
  { re: /\b(?:dab\s*mphei|mphei)\s*(?:buon|four|4)\b/gi, num: '24' },
  { re: /\b(?:dab\s*mphei|mphei)\s*(?:bei|three|3)\b/gi, num: '23' },
  { re: /\b(?:dab\s*mphei|mphei)\s*(?:pir|two|2)\b/gi, num: '22' },
  { re: /\b(?:dab\s*mphei|mphei)\s*(?:muoy|mouy|one|1)\b/gi, num: '21' },
  { re: /\b(?:dab\s*mphei|mphei)\b/gi, num: '20' },
  // 11-19
  { re: /\bdab\s*(?:bram\s*buon|pram\s*buon|nine|9)\b/gi, num: '19' },
  { re: /\bdab\s*(?:bram\s*bei|pram\s*bei|eight|8)\b/gi, num: '18' },
  { re: /\bdab\s*(?:bram\s*pir|pram\s*pir|seven|7)\b/gi, num: '17' },
  { re: /\bdab\s*(?:bram\s*muoy|pram\s*muoy|six|6)\b/gi, num: '16' },
  { re: /\bdab\s*(?:bram|pram|five|5)\b/gi, num: '15' },
  { re: /\bdab\s*(?:buon|four|4)\b/gi, num: '14' },
  { re: /\bdab\s*(?:bei|three|3)\b/gi, num: '13' },
  { re: /\bdab\s*(?:pir|two|2)\b/gi, num: '12' },
  { re: /\bdab\s*(?:muoy|mouy|one|1)\b/gi, num: '11' },
  { re: /\b(?:dab|ten)\b/gi, num: '10' },
  // 1-9
  { re: /\b(?:pram\s*buon|bram\s*buon|nine)\b/gi, num: '9' },
  { re: /\b(?:pram\s*bei|bram\s*bei|eight)\b/gi, num: '8' },
  { re: /\b(?:pram\s*pir|bram\s*pir|seven)\b/gi, num: '7' },
  { re: /\b(?:pram\s*muoy|bram\s*muoy|six)\b/gi, num: '6' },
  { re: /\b(?:pram|bram|five)\b/gi, num: '5' },
  { re: /\b(?:buon|four)\b/gi, num: '4' },
  { re: /\b(?:bei|three)\b/gi, num: '3' },
  { re: /\b(?:pir|two)\b/gi, num: '2' },
  { re: /\b(?:muoy|mouy|one)\b/gi, num: '1' },
];

@Component({
  selector: 'app-owner-property-form',
  imports: [
    CommonModule,
    FormsModule,
    ReactiveFormsModule,
    RouterLink,
    LeafletMapComponent,
    SearchableSelectComponent,
  ],
  templateUrl: './owner-form.html',
})
export class OwnerPropertyFormComponent implements OnInit {
  readonly id = input<string | undefined>();
  readonly language = inject(LanguageService);
  private readonly platformId = inject(PLATFORM_ID);


  /** Show the English and Khmer label together, e.g. "Property Title / ចំណងជើងអចលនទ្រព្យ". */
  bilingualLabel(key: string): string {
    return `${this.language.tIn('en', key)} / ${this.language.tIn('km', key)}`;
  }

  /** Same as {@link bilingualLabel}, used for input placeholders. */
  bilingualPlaceholder(key: string): string {
    return this.bilingualLabel(key);
  }

  private readonly categorySettings = signal<PropertyCategorySetting[]>([]);
  categoryLoadError = signal(false);
  readonly categoryOptions = computed<SelectOption[]>(() => [
    { value: '', label: this.language.t('ownerForm.uncategorized') },
    ...this.categorySettings().map((category) => ({
      value: category.value,
      label: this.language.current() === 'km' ? category.label_km : category.label_en,
    })),
  ]);

  private readonly additionalLocations = signal<SelectOption[]>([]);
  private readonly cambodiaProvinces = signal<CambodiaProvince[]>([]);
  private readonly cambodiaDistricts = signal<CambodiaDistrict[]>([]);
  private readonly cambodiaCommunes = signal<CambodiaCommune[]>([]);
  private readonly cambodiaVillages = signal<CambodiaVillage[]>([]);
  provinceCode = signal('');
  communeCode = signal('');
  villageCode = signal('');
  private districtCode = signal('');
  districtLoadError = signal(false);
  locationLoadError = signal(false);
  private provincesLoaded = false;
  private districtsLoaded = false;
  private communesLoaded = false;
  private villagesRequested = false;
  private villagesLoaded = false;
  private pendingMapData: {
    address?: Record<string, string>;
    displayName?: string;
  } | null = null;
  private pendingAiLocation: {
    location?: string;
    province?: string;
    commune?: string;
    village?: string;
  } | null = null;

  readonly provinceOptions = computed<SelectOption[]>(() =>
    this.cambodiaProvinces().map((province) => ({
      value: province.code,
      label: this.locationLabel(province.name_en, province.name_km),
    })),
  );

  readonly locationOptions = computed<SelectOption[]>(() => {
    const fallbackLocations: [string, string][] = [
      ['Phnom Penh - BKK1', 'ភ្នំពេញ - បឹងកេងកង ១'],
      ['Phnom Penh - Toul Kork', 'ភ្នំពេញ - ទួលគោក'],
      ['Phnom Penh - Tuol Khmao', 'ភ្នំពេញ - ទួលខ្មៅ'],
      ['Phnom Penh - Chroy Changvar', 'ភ្នំពេញ - ជ្រោយចង្វារ'],
      ['Phnom Penh - Daun Penh', 'ភ្នំពេញ - ដូនពេញ'],
      ['Siem Reap - Wat Bo', 'សៀមរាប - វត្តបូព៌'],
    ];
    const province = this.provinceCode();
    const districts = this.cambodiaDistricts().filter(
      (district) => !province || district.province_code === province,
    );
    const options = districts.length
      ? districts.map((district) => {
          const bilingualName = this.locationLabel(district.name_en, district.name_km);
          return { value: bilingualName, label: bilingualName };
        })
      : fallbackLocations.map(([value, khmer]) => ({
          value,
          label: this.locationLabel(value, khmer),
        }));
    for (const location of this.additionalLocations()) {
      if (!options.some((option) => option.value === location.value)) {
        options.push({
          value: location.value,
          label: location.label,
        });
      }
    }
    return options;
  });

  readonly communeOptions = computed<SelectOption[]>(() => {
    const province = this.provinceCode();
    const district = this.districtCode();
    return this.cambodiaCommunes()
      .filter(
        (commune) =>
          (!province || commune.province_code === province) &&
          (!district || commune.district_code === district),
      )
      .map((commune) => ({
        value: commune.code,
        label: this.locationLabel(commune.name_en, commune.name_km),
      }));
  });

  readonly villageOptions = computed<SelectOption[]>(() => {
    const commune = this.communeCode();
    if (!commune) return [];
    return this.cambodiaVillages()
      .filter((village) => village.commune_code === commune)
      .map((village) => ({
        value: this.villageKey(village),
        label: this.locationLabel(village.name_en, village.name_km),
      }));
  });

  private villageKey(village: CambodiaVillage): string {
    return `${village.code}|${village.name_en}|${village.name_km}`;
  }

  private locationLabel(nameEn: string, nameKm: string): string {
    return nameEn && nameKm ? `${nameEn} / ${nameKm}` : nameEn || nameKm;
  }

  private normalizeLocationName(value: string): string {
    return value.trim().toLowerCase().replace(/\s+/g, ' ');
  }

  private findLocationByName<T extends { name_en: string; name_km: string }>(
    items: T[],
    value: string,
  ): T | undefined {
    const query = this.normalizeLocationName(value);
    if (!query) return undefined;
    return items.find(
      (item) =>
        this.normalizeLocationName(item.name_en) === query ||
        this.normalizeLocationName(item.name_km) === query,
    );
  }

  private readonly fb = inject(FormBuilder);
  private readonly propertyService = inject(PropertyService);
  private readonly router = inject(Router);

  isEdit = signal(false);
  isLoading = signal(false);
  isUploadingPhotos = signal(false);
  isGeneratingDescription = signal(false);
  aiPrompt = '';
  aiPanelOpen = signal(false);
  aiDraftApplied = signal(false);
  errorMessage = signal<string | null>(null);
  selectedImages = signal<string[]>([]);
  existingImages = signal<string[]>([]);

  latitude = signal<number | null>(null);
  longitude = signal<number | null>(null);
  private loadedProperty: Property | null = null;
  coordError = signal(false);
  isResolvingCoordinates = signal(false);
  isReverseGeocoding = signal(false);
  mapAddressMatched = signal(false);
  mapAddressNotFound = signal(false);
  private coordinateResolveTimer: ReturnType<typeof setTimeout> | null = null;
  private coordinateResolveRequest = 0;
  private reverseGeocodeTimer: ReturnType<typeof setTimeout> | null = null;
  private reverseGeocodeRequest = 0;
  private lastReverseGeocodeAt = 0;

  form = this.fb.group({
    title: [''],
    title_km: [''],
    location: [''],
    price_per_month: [500, [Validators.required, Validators.min(1)]],
    category: [''],
    bedrooms: [1, [Validators.required, Validators.min(0)]],
    bathrooms: [1, [Validators.required, Validators.min(0)]],
    description: [''],
    description_km: [''],
    coordinates: [''],
  });

  ngOnInit(): void {
    this.form.controls.location.valueChanges.subscribe((value) =>
      this.onDistrictChange(value || ''),
    );
    if (isPlatformBrowser(this.platformId)) {
      this.loadCategorySettings();
      this.loadDistricts();
      this.loadProvinces();
      this.loadCommunes();
      this.loadVillages();
    }
    const editId = this.id();
    if (editId) {
      this.isEdit.set(true);
      this.loadProperty(Number(editId));
    }
  }

  loadCategorySettings(): void {
    if (!isPlatformBrowser(this.platformId)) return;
    this.categoryLoadError.set(false);
    this.propertyService.getCategories().subscribe({
      next: (res) => this.categorySettings.set(res.categories || []),
      error: () => this.categoryLoadError.set(true),
    });
  }

  loadDistricts(): void {
    if (!isPlatformBrowser(this.platformId)) return;
    this.districtLoadError.set(false);
    this.propertyService.getCambodiaDistricts().subscribe({
      next: (districts) => {
        this.districtsLoaded = true;
        this.cambodiaDistricts.set(districts);
        this.districtLoadError.set(districts.length === 0);
        this.applyLoadedPropertyLocation();
        this.applyPendingMapAddress();
      },
      error: () => this.districtLoadError.set(true),
    });
  }

  loadProvinces(): void {
    if (!isPlatformBrowser(this.platformId)) return;
    this.propertyService.getCambodiaProvinces().subscribe({
      next: (provinces) => {
        this.provincesLoaded = true;
        this.cambodiaProvinces.set(provinces);
        this.locationLoadError.set(provinces.length === 0);
        this.applyLoadedPropertyLocation();
        this.applyPendingMapAddress();
      },
      error: () => this.locationLoadError.set(true),
    });
  }

  loadCommunes(): void {
    if (!isPlatformBrowser(this.platformId)) return;
    this.propertyService.getCambodiaCommunes().subscribe({
      next: (communes) => {
        this.communesLoaded = true;
        this.cambodiaCommunes.set(communes);
        this.applyLoadedPropertyLocation();
        this.applyPendingMapAddress();
      },
      error: () => this.locationLoadError.set(true),
    });
  }

  loadVillages(): void {
    if (!isPlatformBrowser(this.platformId)) return;
    this.villagesRequested = true;
    this.propertyService.getCambodiaVillages().subscribe({
      next: (villages) => {
        this.villagesLoaded = true;
        this.cambodiaVillages.set(villages);
        this.applyLoadedPropertyLocation();
        this.applyPendingMapAddress();
        if (this.communeCode() && !this.villageCode()) {
          const communeVillages = villages.filter(
            (v) => v.commune_code === this.communeCode(),
          );
          if (communeVillages.length > 0) {
            this.villageCode.set(this.villageKey(communeVillages[0]));
          }
        }
        if (this.pendingAiLocation) {
          this.applyAiLocation(this.pendingAiLocation);
        }
      },
      error: () => {
        this.villagesRequested = false;
        this.villagesLoaded = false;
        this.pendingMapData = null;
        this.locationLoadError.set(true);
      },
    });
  }

  onProvinceChange(code: string): void {
    this.cancelMapAddressLookup();
    this.provinceCode.set(code);
    this.districtCode.set('');
    this.communeCode.set('');
    this.villageCode.set('');
    this.form.patchValue({ location: '' });
  }

  onDistrictChange(value: string): void {
    this.cancelMapAddressLookup();
    const district = this.findDistrictByName(value);
    this.districtCode.set(district?.code || '');
    if (district) this.provinceCode.set(district.province_code);
    this.communeCode.set('');
    this.villageCode.set('');
  }

  onCommuneChange(code: string): void {
    this.cancelMapAddressLookup();
    this.communeCode.set(code);
    this.villageCode.set('');
    if (code) {
      this.ensureVillagesLoaded();
      if (this.villagesLoaded) {
        const communeVillages = this.cambodiaVillages().filter(
          (v) => v.commune_code === code,
        );
        if (communeVillages.length > 0) {
          this.villageCode.set(this.villageKey(communeVillages[0]));
        }
      }
    }
  }

  private ensureVillagesLoaded(): void {
    if (this.villagesRequested) return;
    this.loadVillages();
  }

  private findDistrictByName(value: string): CambodiaDistrict | undefined {
    if (!value) return undefined;
    return this.cambodiaDistricts().find(
      (district) => this.locationLabel(district.name_en, district.name_km) === value,
    );
  }

  private applyLoadedPropertyLocation(): void {
    const property = this.loadedProperty;
    if (!property) return;
    const district = this.findDistrictByName(
      property.location || property.location_km || '',
    );
    const province = this.cambodiaProvinces().find(
      (item) =>
        (property.province && item.name_en === property.province) ||
        (property.province_km && item.name_km === property.province_km),
    );
    const commune = this.cambodiaCommunes().find(
      (item) =>
        ((property.commune && item.name_en === property.commune) ||
          (property.commune_km && item.name_km === property.commune_km)) &&
        (!district || item.district_code === district.code),
    );
    const village = this.cambodiaVillages().find(
      (item) =>
        ((property.village && item.name_en === property.village) ||
          (property.village_km && item.name_km === property.village_km)) &&
        (!commune || item.commune_code === commune.code),
    );
    this.districtCode.set(district?.code || '');
    this.provinceCode.set(province?.code || district?.province_code || '');
    this.communeCode.set(commune?.code || '');
    this.villageCode.set(village ? this.villageKey(village) : '');
    if (commune) this.ensureVillagesLoaded();
  }

  loadProperty(id: number): void {
    this.isLoading.set(true);
    this.propertyService.getPublicProperty(id).subscribe({
      next: (res) => {
        this.isLoading.set(false);
        const p = res.property;
        this.loadedProperty = p;
        const location = p.location || p.location_km || '';
        if (location && !this.locationOptions().some((option) => option.value === location)) {
          this.additionalLocations.update((items) => [
            ...items.filter((item) => item.value !== location),
            {
              value: location,
              label: p.location_km ? `${location} / ${p.location_km}` : location,
            },
          ]);
        }
        this.form.patchValue({
          title: p.title,
          title_km: p.title_km || '',
          location,
          price_per_month: p.price_per_month,
          category: p.category || '',
          bedrooms: p.bedrooms,
          bathrooms: p.bathrooms,
          description: p.description,
          description_km: p.description_km || '',
          coordinates: formatCoordinates(p.latitude, p.longitude),
        });
        this.applyLoadedPropertyLocation();
        this.existingImages.set(p.images || []);
        this.latitude.set(p.latitude ?? null);
        this.longitude.set(p.longitude ?? null);
      },
      error: () => this.isLoading.set(false),
    });
  }

  /** Handle direct clipboard paste for fast coordinate resolution. */
  onCoordinatesPaste(event: ClipboardEvent): void {
    const text = event.clipboardData?.getData('text') || '';
    if (text.trim()) {
      event.preventDefault();
      this.form.patchValue({ coordinates: text.trim() });
      this.onCoordinatesInput();
    }
  }

  /** Parse a pasted "lat, lng" or maps URL into the map pin. */
  onCoordinatesInput(): void {
    const requestId = ++this.coordinateResolveRequest;
    if (this.coordinateResolveTimer) clearTimeout(this.coordinateResolveTimer);
    this.isResolvingCoordinates.set(false);
    this.cancelMapAddressLookup();
    const raw = (this.form.get('coordinates')?.value || '').trim();
    if (!raw) {
      this.latitude.set(null);
      this.longitude.set(null);
      this.coordError.set(false);
      return;
    }

    const parsed = parseCoordinates(raw);
    if (parsed) {
      this.latitude.set(parsed.latitude);
      this.longitude.set(parsed.longitude);
      this.coordError.set(false);
      if (
        raw.includes('http') ||
        raw.includes('maps') ||
        raw.includes('<iframe') ||
        raw.includes('°')
      ) {
        this.form.patchValue(
          { coordinates: formatCoordinates(parsed.latitude, parsed.longitude) },
          { emitEvent: false },
        );
      }
      this.scheduleMapAddressLookup(parsed.latitude, parsed.longitude, 100);
      return;
    }

    if (
      raw.includes('maps.app.goo.gl') ||
      raw.includes('goo.gl') ||
      raw.includes('google.com') ||
      raw.includes('maps.google') ||
      raw.startsWith('http')
    ) {
      this.coordError.set(false);
      this.coordinateResolveTimer = setTimeout(() => {
        this.isResolvingCoordinates.set(true);
        this.propertyService.resolveGoogleMapsUrl(raw).subscribe({
          next: (point) => {
            if (requestId !== this.coordinateResolveRequest) return;
            this.latitude.set(point.latitude);
            this.longitude.set(point.longitude);
            this.form.patchValue(
              { coordinates: formatCoordinates(point.latitude, point.longitude) },
              { emitEvent: false },
            );
            this.isResolvingCoordinates.set(false);
            this.coordError.set(false);
            this.scheduleMapAddressLookup(point.latitude, point.longitude, 100);
          },
          error: () => {
            if (requestId !== this.coordinateResolveRequest) return;
            this.isResolvingCoordinates.set(false);
            this.coordError.set(true);
          },
        });
      }, 200);
      return;
    }

    this.coordError.set(false);
  }

  /** Move the pin from a map click / drag. */
  onMapPick(point: { latitude: number; longitude: number }): void {
    this.coordinateResolveRequest++;
    if (this.coordinateResolveTimer) clearTimeout(this.coordinateResolveTimer);
    this.isResolvingCoordinates.set(false);
    this.cancelMapAddressLookup();
    this.latitude.set(point.latitude);
    this.longitude.set(point.longitude);
    this.coordError.set(false);
    this.form.patchValue(
      { coordinates: formatCoordinates(point.latitude, point.longitude) },
      { emitEvent: false },
    );
    this.scheduleMapAddressLookup(point.latitude, point.longitude, 200);
  }

  clearCoordinates(): void {
    this.coordinateResolveRequest++;
    if (this.coordinateResolveTimer) clearTimeout(this.coordinateResolveTimer);
    this.isResolvingCoordinates.set(false);
    this.cancelMapAddressLookup();
    this.latitude.set(null);
    this.longitude.set(null);
    this.coordError.set(false);
    this.form.patchValue({ coordinates: '' }, { emitEvent: false });
  }

  private scheduleMapAddressLookup(
    latitude: number,
    longitude: number,
    delay = 300,
  ): void {
    if (!isPlatformBrowser(this.platformId)) return;
    const requestId = ++this.reverseGeocodeRequest;
    if (this.reverseGeocodeTimer) clearTimeout(this.reverseGeocodeTimer);
    this.isReverseGeocoding.set(false);
    this.mapAddressMatched.set(false);
    this.mapAddressNotFound.set(false);
    const wait = Math.max(
      delay,
      400 - (Date.now() - this.lastReverseGeocodeAt),
    );
    this.reverseGeocodeTimer = setTimeout(() => {
      this.lastReverseGeocodeAt = Date.now();
      this.isReverseGeocoding.set(true);
      this.propertyService.reverseGeocode(latitude, longitude).subscribe({
        next: (result) => {
          if (requestId !== this.reverseGeocodeRequest) return;
          this.isReverseGeocoding.set(false);
          const outcome = this.applyAddressFromOpenStreetMap(
            result.address,
            result.display_name,
          );
          this.mapAddressMatched.set(outcome === 'applied');
          this.mapAddressNotFound.set(outcome === 'unmatched');
        },
        error: () => {
          if (requestId !== this.reverseGeocodeRequest) return;
          this.isReverseGeocoding.set(false);
          this.mapAddressMatched.set(false);
          this.mapAddressNotFound.set(true);
        },
      });
    }, wait);
  }

  private cancelMapAddressLookup(): void {
    this.reverseGeocodeRequest++;
    if (this.reverseGeocodeTimer) clearTimeout(this.reverseGeocodeTimer);
    this.reverseGeocodeTimer = null;
    this.isReverseGeocoding.set(false);
    this.mapAddressMatched.set(false);
    this.mapAddressNotFound.set(false);
    this.pendingMapData = null;
  }

  private applyAddressFromOpenStreetMap(
    address: Record<string, string> | undefined,
    displayName?: string,
  ): 'applied' | 'pending' | 'unmatched' {
    if (!address && !displayName) return 'unmatched';
    const country = ((address && address['country_code']) || '').toLowerCase();
    if (country && country !== 'kh') return 'unmatched';
    if (!this.provincesLoaded || !this.districtsLoaded || !this.communesLoaded) {
      this.pendingMapData = { address, displayName };
      return 'pending';
    }

    const addr = address || {};
    const postcode = (addr['postcode'] || '').trim().replace(/[^0-9]/g, '');

    const parts = (displayName || '').split(',').map((s) => s.trim());
    const allCandidates = [
      ...Object.values(addr),
      ...parts,
    ].filter(
      (v): v is string => typeof v === 'string' && v.trim().length > 1,
    );

    if (!allCandidates.length && !postcode) {
      return 'unmatched';
    }

    let province: CambodiaProvince | undefined;
    let district: CambodiaDistrict | undefined;
    let commune: CambodiaCommune | undefined;
    let village: CambodiaVillage | undefined;

    // 1. Province matching
    for (const cand of allCandidates) {
      const norm = this.normalizeAdministrativeText(cand);
      if (!norm) continue;
      province = this.cambodiaProvinces().find(
        (p) =>
          this.normalizeAdministrativeText(p.name_en) === norm ||
          this.normalizeAdministrativeText(p.name_km) === norm,
      );
      if (province) break;
    }
    if (!province) {
      const isoCode = (addr['ISO3166-2-lvl4'] || addr['ISO3166-2'] || '').trim();
      const m = /^KH-(\d{1,2})$/i.exec(isoCode);
      if (m) {
        const code = m[1].padStart(2, '0');
        province = this.cambodiaProvinces().find((p) => p.code === code);
      }
    }
    if (!province && postcode.length >= 2) {
      province = this.cambodiaProvinces().find(
        (p) => p.code === postcode.slice(0, 2),
      );
    }

    // 2. Commune matching (name match first)
    for (const cand of allCandidates) {
      const norm = this.normalizeAdministrativeText(cand);
      if (!norm) continue;
      commune = this.cambodiaCommunes().find((c) => {
        if (province && c.province_code !== province.code) return false;
        return (
          this.normalizeAdministrativeText(c.name_en) === norm ||
          this.normalizeAdministrativeText(c.name_km) === norm
        );
      });
      if (commune) {
        if (!district) {
          district = this.cambodiaDistricts().find(
            (d) => d.code === commune!.district_code,
          );
        }
        if (!province) {
          province = this.cambodiaProvinces().find(
            (p) => p.code === commune!.province_code,
          );
        }
        break;
      }
    }

    // Fallback: Commune by 6-digit NIS postcode
    if (!commune && postcode.length === 6) {
      commune = this.cambodiaCommunes().find((c) => c.code === postcode);
      if (commune) {
        if (!district) {
          district = this.cambodiaDistricts().find(
            (d) => d.code === commune!.district_code,
          );
        }
        if (!province) {
          province = this.cambodiaProvinces().find(
            (p) => p.code === commune!.province_code,
          );
        }
      }
    }

    // 3. District matching (if not deduced from commune)
    if (!district) {
      for (const cand of allCandidates) {
        const norm = this.normalizeAdministrativeText(cand);
        if (!norm) continue;
        district = this.cambodiaDistricts().find((d) => {
          if (province && d.province_code !== province.code) return false;
          return (
            this.normalizeAdministrativeText(d.name_en) === norm ||
            this.normalizeAdministrativeText(d.name_km) === norm
          );
        });
        if (district) {
          if (!province) {
            province = this.cambodiaProvinces().find(
              (p) => p.code === district!.province_code,
            );
          }
          break;
        }
      }
    }
    // Fallback: District by 4-digit NIS postcode
    if (!district && postcode.length >= 4) {
      district = this.cambodiaDistricts().find(
        (d) => d.code === postcode.slice(0, 4),
      );
      if (district && !province) {
        province = this.cambodiaProvinces().find(
          (p) => p.code === district!.province_code,
        );
      }
    }

    // 4. Village matching
    if (commune && this.villagesLoaded) {
      const communeVillages = this.cambodiaVillages().filter(
        (v) => v.commune_code === commune!.code,
      );
      // 4a. Exact normalized match
      for (const cand of allCandidates) {
        const norm = this.normalizeAdministrativeText(cand);
        if (!norm) continue;
        village = communeVillages.find(
          (v) =>
            this.normalizeAdministrativeText(v.name_en) === norm ||
            this.normalizeAdministrativeText(v.name_km) === norm,
        );
        if (village) break;
      }
      // 4b. Substring / partial match
      if (!village) {
        for (const cand of allCandidates) {
          const norm = this.normalizeAdministrativeText(cand);
          if (!norm) continue;
          village = communeVillages.find((v) => {
            const vEn = this.normalizeAdministrativeText(v.name_en);
            const vKm = this.normalizeAdministrativeText(v.name_km);
            return (
              (vEn && (norm.includes(vEn) || vEn.includes(norm))) ||
              (vKm && (norm.includes(vKm) || vKm.includes(norm)))
            );
          });
          if (village) break;
        }
      }
      // 4c. Always auto-complete to the first village of the commune if no specific village is found
      if (!village && communeVillages.length > 0) {
        village = communeVillages[0];
      }
    }

    if (!province && !district && !commune && !village) {
      return 'unmatched';
    }

    this.form.patchValue(
      {
        location: district
          ? this.locationLabel(district.name_en, district.name_km)
          : '',
      },
      { emitEvent: false },
    );
    this.provinceCode.set(province?.code || district?.province_code || '');
    this.districtCode.set(district?.code || '');
    this.communeCode.set(commune?.code || '');
    this.villageCode.set(village ? this.villageKey(village) : '');

    if (commune && !this.villagesLoaded) {
      this.pendingMapData = { address, displayName };
      this.ensureVillagesLoaded();
    }
    return 'applied';
  }

  private applyPendingMapAddress(): void {
    if (
      !this.pendingMapData ||
      !this.provincesLoaded ||
      !this.districtsLoaded ||
      !this.communesLoaded
    ) {
      return;
    }
    const data = this.pendingMapData;
    this.pendingMapData = null;
    const outcome = this.applyAddressFromOpenStreetMap(
      data.address,
      data.displayName,
    );
    this.mapAddressMatched.set(outcome === 'applied');
    this.mapAddressNotFound.set(outcome === 'unmatched');
  }

  private normalizeAdministrativeText(val: string): string {
    if (!val) return '';
    let s = val.normalize('NFKC').toLowerCase();
    // Convert Khmer digits to Arabic digits
    s = s.replace(/[០-៩]/gu, (d) => KHMER_DIGITS[d] || d);
    s = s.replace(ADMIN_NAME_PREFIX, '');
    s = s.replace(ADMIN_NAME_SUFFIX, '');
    s = s.replace(/sihanoukville|mittapheap|kampong\s*saom/gui, 'preah sihanouk');
    s = s.replace(
      /7\s*makara|prampi\s*makara|pram\s*pir\s*makara|7\s*meakkakra/gui,
      'prampir meakkakra',
    );
    s = s.replace(/toul\s*kork|tuol\s*kork/gui, 'tuol kouk');
    s = s.replace(/chroy\s*changvar|chroy\s*changva/gui, 'chraoy chongvar');
    s = s.replace(/daun\s*penh/gui, 'doun penh');
    s = s.replace(/sen\s*sok/gui, 'saen sokh');
    s = s.replace(/russey\s*keo|russei\s*kaev/gui, 'russei keo');
    s = s.replace(/pur\s*senchey|por\s*sen\s*chey/gui, 'pou saen chey');
    s = s.replace(/prek\s*pnov/gui, 'preaek pnov');
    s = s.replace(/kambol/gui, 'kamboul');
    s = s.replace(/siem\s*reap/gui, 'siem reab');

    // Common phonetic / romanization spelling differences in Khmer names
    s = s.replace(/thnaot/gui, 'tnaot');
    s = s.replace(/thmor|thmar/gui, 'tmar');
    s = s.replace(/chhouk|chhook|chuk/gui, 'chhuk');
    s = s.replace(/trapeang/gui, 'tropeang');
    s = s.replace(/boeung/gui, 'boeng');
    s = s.replace(/toul/gui, 'tuol');
    s = s.replace(/kork/gui, 'kouk');
    s = s.replace(/prek/gui, 'preaek');
    s = s.replace(/stung/gui, 'steung');
    s = s.replace(/slaket/gui, 'sla ket');
    s = s.replace(/chamkar/gui, 'chomkar');

    // Strip prefix markers before numbers like "ti 1", "lekh 1", "quarter 1", "group 1", "no 1"
    s = s.replace(/\b(?:ti|lekh|quarter|group|no\.?)\s*(\d+)\b/gui, '$1');

    // Convert number words to digits
    for (const { re, num } of NUMBER_MAPPINGS) {
      s = s.replace(re, num);
    }

    return s.replace(/[^\p{L}\p{N}]+/gu, '').trim();
  }

  async onImagesSelected(event: Event): Promise<void> {
    const input = event.target as HTMLInputElement;
    const files = Array.from(input.files || []);
    const remaining = Math.max(0, 12 - this.existingImages().length - this.selectedImages().length);
    if (files.length > remaining) {
      this.errorMessage.set('You can add up to 12 photos.');
      input.value = '';
      return;
    }
    if (!files.length) return;

    this.isUploadingPhotos.set(true);
    this.errorMessage.set(null);
    try {
      const prepared = await Promise.all(
        files.map((file) => {
          if (!file.type.startsWith('image/')) throw new Error('not_image');
          if (file.size > 15 * 1024 * 1024) throw new Error('file_too_large');
          return compressImageToFile(file, 1280, 0.72, 100_000);
        }),
      );
      const res = await firstValueFrom(this.propertyService.uploadPropertyImages(prepared));
      this.selectedImages.update((images) => [...images, ...res.urls]);
    } catch (error) {
      this.errorMessage.set(this.imageUploadError(error));
    } finally {
      this.isUploadingPhotos.set(false);
      input.value = '';
    }
  }

  private imageUploadError(error: unknown): string {
    if (error instanceof Error) {
      if (error.message === 'not_image') return 'Please choose image files only.';
      if (error.message === 'file_too_large') return 'Each photo must be 15 MB or smaller.';
      if (error.message === 'image_unreadable') return 'Could not open a selected photo.';
      if (error.message === 'image_too_large') return 'A photo could not be compressed enough.';
    }
    const detail = (error as { error?: { detail?: string } })?.error?.detail;
    if (detail === 'image_too_large') return 'Each photo must be 15 MB or smaller.';
    if (detail === 'invalid_image_file') return 'Please choose a valid image file.';
    return 'Could not upload the selected photos. Please try again.';
  }

  removeSelectedImage(index: number): void {
    this.selectedImages.update((images) => images.filter((_, i) => i !== index));
  }

  removeExistingImage(index: number): void {
    this.existingImages.update((images) => images.filter((_, i) => i !== index));
  }

  generateWithAi(): void {
    if (this.isGeneratingDescription()) return;
    if (!this.aiPrompt.trim()) {
      this.errorMessage.set(this.language.t('ownerForm.aiNeedsPrompt'));
      return;
    }
    this.loadCategorySettings();
    this.isGeneratingDescription.set(true);
    this.errorMessage.set(null);
    this.aiDraftApplied.set(false);

    this.propertyService
      .generateDescription({
        prompt: this.aiPrompt.trim(),
        locations: this.locationOptions().map((option) => option.value).filter(Boolean),
        categories: this.categorySettings().map((category) => category.value),
      })
      .subscribe({
        next: (res) => {
          this.isGeneratingDescription.set(false);
          this.aiDraftApplied.set(true);
          this.form.patchValue({
            ...(res.title ? { title: res.title } : {}),
            ...(res.title_km ? { title_km: res.title_km } : {}),
            ...(res.price_per_month != null ? { price_per_month: res.price_per_month } : {}),
            ...(res.category && this.categorySettings().some((category) => category.value === res.category) ? { category: res.category } : {}),
            ...(res.bedrooms != null ? { bedrooms: res.bedrooms } : {}),
            ...(res.bathrooms != null ? { bathrooms: res.bathrooms } : {}),
            ...(res.description ? { description: res.description } : {}),
            ...(res.description_km ? { description_km: res.description_km } : {}),
          });
          this.applyAiLocation(res);
        },
        error: (err) => {
          this.isGeneratingDescription.set(false);
          const detail = err?.error?.detail;
          if (detail === 'ai_not_configured') {
            this.errorMessage.set(this.language.t('ownerForm.aiNotConfigured'));
          } else {
            this.errorMessage.set(this.language.t('ownerForm.aiGenerationFailed'));
          }
        },
      });
  }

  private applyAiLocation(draft: {
    location?: string;
    province?: string;
    commune?: string;
    village?: string;
  }): void {
    const locationValue = (draft.location || '').trim();
    const provinceValue = (draft.province || '').trim();
    const communeValue = (draft.commune || '').trim();
    const villageValue = (draft.village || '').trim();

    if (!locationValue && !provinceValue && !communeValue && !villageValue) {
      this.pendingAiLocation = null;
      return;
    }

    let district = this.cambodiaDistricts().find(
      (item) =>
        locationValue !== '' &&
        this.locationLabel(item.name_en, item.name_km) === locationValue,
    );
    if (!district && locationValue) {
      district = this.findLocationByName(this.cambodiaDistricts(), locationValue);
    }
    let province = provinceValue
      ? this.findLocationByName(this.cambodiaProvinces(), provinceValue)
      : undefined;
    let commune = communeValue
      ? this.findLocationByName(
          this.cambodiaCommunes().filter(
            (item) =>
              (!district || item.district_code === district.code) &&
              (!province || item.province_code === province.code),
          ),
          communeValue,
        )
      : undefined;
    let village =
      villageValue && this.cambodiaVillages().length
        ? this.findLocationByName(
            this.cambodiaVillages().filter(
              (item) => !commune || item.commune_code === commune.code,
            ),
            villageValue,
          )
        : undefined;

    if (!commune && village) {
      const communeCode = village.commune_code;
      commune = this.cambodiaCommunes().find((item) => item.code === communeCode);
    }
    if (!district && commune) {
      const districtCode = commune.district_code;
      district = this.cambodiaDistricts().find((item) => item.code === districtCode);
    }
    if (!province && commune) {
      const provinceCode = commune.province_code;
      province = this.cambodiaProvinces().find((item) => item.code === provinceCode);
    }
    if (!province && district) {
      const provinceCode = district.province_code;
      province = this.cambodiaProvinces().find((item) => item.code === provinceCode);
    }

    const districtLabel = district
      ? this.locationLabel(district.name_en, district.name_km)
      : '';
    this.form.patchValue({ location: districtLabel });

    this.provinceCode.set(province?.code || '');
    this.districtCode.set(district?.code || '');
    this.communeCode.set(commune?.code || '');
    this.villageCode.set(village ? this.villageKey(village) : '');

    if (commune || (villageValue && !this.cambodiaVillages().length)) {
      this.ensureVillagesLoaded();
    }
    this.pendingAiLocation =
      villageValue && !this.cambodiaVillages().length ? draft : null;
  }

  onSubmit(): void {
    const val = this.form.value;
    if (!val.title?.trim() && !val.title_km?.trim()) {
      this.errorMessage.set(this.language.t('ownerForm.titleRequired'));
      return;
    }
    if (!val.location?.trim()) {
      this.errorMessage.set(this.language.t('ownerForm.locationRequired'));
      return;
    }
    if (this.form.invalid) return;
    if (this.isUploadingPhotos()) {
      this.errorMessage.set('Please wait for the photos to finish uploading.');
      return;
    }

    this.isLoading.set(true);
    this.errorMessage.set(null);

    const province = this.cambodiaProvinces().find(
      (item) => item.code === this.provinceCode(),
    );
    const commune = this.cambodiaCommunes().find(
      (item) => item.code === this.communeCode(),
    );
    const village = this.cambodiaVillages().find(
      (item) => this.villageKey(item) === this.villageCode(),
    );

    const payload = {
      title: val.title || '',
      title_km: val.title_km || '',
      province: province?.name_en || '',
      province_km: province?.name_km || '',
      location: val.location || '',
      location_km: '',
      commune: commune?.name_en || '',
      commune_km: commune?.name_km || '',
      village: village?.name_en || '',
      village_km: village?.name_km || '',
      price_per_month: Number(val.price_per_month) || 0,
      category: val.category || '',
      bedrooms: Number(val.bedrooms) || 0,
      bathrooms: Number(val.bathrooms) || 0,
      description: val.description || '',
      description_km: val.description_km || '',
      latitude: this.latitude(),
      longitude: this.longitude(),
      images: [...this.existingImages(), ...this.selectedImages()],
    };

    const editId = this.id();
    if (editId) {
      this.propertyService.updateProperty(Number(editId), payload).subscribe({
        next: () => {
          this.isLoading.set(false);
          this.router.navigate(['/owner/properties']);
        },
        error: (err) => {
          this.isLoading.set(false);
          this.errorMessage.set(err.error?.detail || 'Failed to update property.');
        },
      });
    } else {
      this.propertyService.createProperty(payload).subscribe({
        next: () => {
          this.isLoading.set(false);
          this.router.navigate(['/owner/properties']);
        },
        error: (err) => {
          this.isLoading.set(false);
          this.errorMessage.set(
            this.requestError(err, 'Failed to create property.')
          );
        },
      });
    }
  }

  private requestError(err: any, fallback: string): string {
    const detail = err?.error?.detail;
    if (typeof detail === 'string' && detail.trim()) return detail;
    if (typeof detail === 'object' && detail !== null) {
      return Object.values(detail).flat().map(String).join(' ');
    }
    return err?.status ? `${fallback} (HTTP ${err.status})` : fallback;
  }
}
