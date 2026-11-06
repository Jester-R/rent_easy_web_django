import { Component, computed, inject, input, OnInit, PLATFORM_ID, signal } from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { CambodiaDistrict, PropertyService } from '../../../services/property.service';
import { LanguageService } from '../../../services/language.service';
import { LeafletMapComponent } from '../../../components/leaflet-map/leaflet-map';
import {
  SearchableSelectComponent,
  SelectOption,
} from '../../../components/searchable-select/searchable-select';
import { PropertyCategorySetting } from '../../../models';
import { formatCoordinates, parseCoordinates } from '../../../shared/coords';
import { compressImageToFile } from '../../../shared/image';

@Component({
  selector: 'app-owner-property-form',
  imports: [
    CommonModule,
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
  private readonly cambodiaDistricts = signal<CambodiaDistrict[]>([]);
  districtLoadError = signal(false);
  readonly locationOptions = computed<SelectOption[]>(() => {
    const fallbackLocations: [string, string][] = [
      ['Phnom Penh - BKK1', 'ភ្នំពេញ - បឹងកេងកង ១'],
      ['Phnom Penh - Toul Kork', 'ភ្នំពេញ - ទួលគោក'],
      ['Phnom Penh - Tuol Khmao', 'ភ្នំពេញ - ទួលខ្មៅ'],
      ['Phnom Penh - Chroy Changvar', 'ភ្នំពេញ - ជ្រោយចង្វារ'],
      ['Phnom Penh - Daun Penh', 'ភ្នំពេញ - ដូនពេញ'],
      ['Siem Reap - Wat Bo', 'សៀមរាប - វត្តបូព៌'],
    ];
    const districts = this.cambodiaDistricts();
    const options = districts.length
      ? districts.map((district) => {
          const bilingualName = `${district.name_en} / ${district.name_km}`;
          return { value: bilingualName, label: bilingualName };
        })
      : fallbackLocations.map(([value, khmer]) => ({
          value,
          label: `${value} / ${khmer}`,
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
  coordError = signal(false);
  isResolvingCoordinates = signal(false);
  private coordinateResolveTimer: ReturnType<typeof setTimeout> | null = null;
  private coordinateResolveRequest = 0;

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
    if (isPlatformBrowser(this.platformId)) {
      this.loadCategorySettings();
      this.loadDistricts();
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
        this.cambodiaDistricts.set(districts);
        this.districtLoadError.set(districts.length === 0);
      },
      error: () => this.districtLoadError.set(true),
    });
  }

  loadProperty(id: number): void {
    this.isLoading.set(true);
    this.propertyService.getPublicProperty(id).subscribe({
      next: (res) => {
        this.isLoading.set(false);
        const p = res.property;
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
        this.existingImages.set(p.images || []);
        this.latitude.set(p.latitude ?? null);
        this.longitude.set(p.longitude ?? null);
      },
      error: () => this.isLoading.set(false),
    });
  }

  /** Parse a pasted "lat, lng" or maps URL into the map pin. */
  onCoordinatesInput(): void {
    const requestId = ++this.coordinateResolveRequest;
    if (this.coordinateResolveTimer) clearTimeout(this.coordinateResolveTimer);
    this.isResolvingCoordinates.set(false);
    const raw = this.form.get('coordinates')?.value || '';
    const parsed = parseCoordinates(raw);
    if (parsed) {
      this.latitude.set(parsed.latitude);
      this.longitude.set(parsed.longitude);
      this.coordError.set(false);
      return;
    }

    if (raw.trim()) {
      const text = raw.trim();
      if (
        text.includes('maps.app.goo.gl') ||
        text.includes('goo.gl/maps') ||
        text.includes('google.com/maps') ||
        text.includes('maps.google.com')
      ) {
        this.coordError.set(false);
        this.coordinateResolveTimer = setTimeout(() => {
          this.isResolvingCoordinates.set(true);
          this.propertyService.resolveGoogleMapsUrl(text).subscribe({
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
            },
            error: () => {
              if (requestId !== this.coordinateResolveRequest) return;
              this.isResolvingCoordinates.set(false);
              this.coordError.set(true);
            },
          });
        }, 350);
        return;
      }
      this.coordError.set(false);
    } else {
      this.latitude.set(null);
      this.longitude.set(null);
      this.coordError.set(false);
    }
  }

  /** Move the pin from a map click / drag. */
  onMapPick(point: { latitude: number; longitude: number }): void {
    this.coordinateResolveRequest++;
    if (this.coordinateResolveTimer) clearTimeout(this.coordinateResolveTimer);
    this.isResolvingCoordinates.set(false);
    this.latitude.set(point.latitude);
    this.longitude.set(point.longitude);
    this.coordError.set(false);
    this.form.patchValue(
      { coordinates: formatCoordinates(point.latitude, point.longitude) },
      { emitEvent: false }
    );
  }

  clearCoordinates(): void {
    this.coordinateResolveRequest++;
    if (this.coordinateResolveTimer) clearTimeout(this.coordinateResolveTimer);
    this.isResolvingCoordinates.set(false);
    this.latitude.set(null);
    this.longitude.set(null);
    this.coordError.set(false);
    this.form.patchValue({ coordinates: '' }, { emitEvent: false });
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
            location: res.location && this.locationOptions().some((option) => option.value === res.location) ? res.location : '',
            ...(res.price_per_month != null ? { price_per_month: res.price_per_month } : {}),
            ...(res.category && this.categorySettings().some((category) => category.value === res.category) ? { category: res.category } : {}),
            ...(res.bedrooms != null ? { bedrooms: res.bedrooms } : {}),
            ...(res.bathrooms != null ? { bathrooms: res.bathrooms } : {}),
            ...(res.description ? { description: res.description } : {}),
            ...(res.description_km ? { description_km: res.description_km } : {}),
          });
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

    const payload = {
      title: val.title || '',
      title_km: val.title_km || '',
      location: val.location || '',
      location_km: '',
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
