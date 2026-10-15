import { Component, computed, inject, input, OnInit, PLATFORM_ID, signal } from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { PropertyService } from '../../../services/property.service';
import { LanguageService } from '../../../services/language.service';
import { LeafletMapComponent } from '../../../components/leaflet-map/leaflet-map';
import {
  SearchableSelectComponent,
  SelectOption,
} from '../../../components/searchable-select/searchable-select';
import { PropertyCategorySetting } from '../../../models';
import { formatCoordinates, parseCoordinates } from '../../../shared/coords';

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
  readonly locationOptions = computed<SelectOption[]>(() => {
    const locations: [string, string][] = [
      ['Phnom Penh - BKK1', 'ភ្នំពេញ - បឹងកេងកង ១'],
      ['Phnom Penh - Toul Kork', 'ភ្នំពេញ - ទួលគោក'],
      ['Phnom Penh - Tuol Khmao', 'ភ្នំពេញ - ទួលខ្មៅ'],
      ['Phnom Penh - Chroy Changvar', 'ភ្នំពេញ - ជ្រោយចង្វារ'],
      ['Phnom Penh - Daun Penh', 'ភ្នំពេញ - ដូនពេញ'],
      ['Siem Reap - Wat Bo', 'សៀមរាប - វត្តបូព៌'],
    ];
    const options = locations.map(([value, khmer]) => ({
      value,
      label: this.language.current() === 'km' ? khmer : value,
    }));
    for (const location of this.additionalLocations()) {
      if (!options.some((option) => option.value === location.value)) {
        options.push({
          value: location.value,
          label: this.language.current() === 'km' ? location.label : location.value,
        });
      }
    }
    return options;
  });

  private readonly fb = inject(FormBuilder);
  private readonly propertyService = inject(PropertyService);
  private readonly router = inject(Router);
  private readonly http = inject(HttpClient);

  isEdit = signal(false);
  isLoading = signal(false);
  errorMessage = signal<string | null>(null);
  selectedImages = signal<string[]>([]);
  existingImages = signal<string[]>([]);

  latitude = signal<number | null>(null);
  longitude = signal<number | null>(null);
  coordError = signal(false);

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
    if (isPlatformBrowser(this.platformId)) this.loadCategorySettings();
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
            { value: location, label: p.location_km || location },
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
      if (text.includes('maps.app.goo.gl') || text.includes('goo.gl/maps') || text.includes('google.com/maps')) {
        // Try to parse from the URL itself or just silently ignore if can't parse
        // Don't show error - just don't set coordinates
        this.coordError.set(false);
        // Try quick patterns
        try {
          const m1 = text.match(/!3d(-?\d+(?:\.\d+)?)!4d(-?\d+(?:\.\d+)?)/i);
          if (m1) {
            const lat = Number(m1[1]);
            const lng = Number(m1[2]);
            if (!isNaN(lat) && !isNaN(lng)) {
              this.latitude.set(lat);
              this.longitude.set(lng);
              this.coordError.set(false);
              this.form.patchValue({ coordinates: formatCoordinates(lat, lng) }, { emitEvent: false });
              return;
            }
          }
          const m2 = text.match(/@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)/);
          if (m2) {
            const lat = Number(m2[1]);
            const lng = Number(m2[2]);
            if (!isNaN(lat) && !isNaN(lng)) {
              this.latitude.set(lat);
              this.longitude.set(lng);
              this.coordError.set(false);
              this.form.patchValue({ coordinates: formatCoordinates(lat, lng) }, { emitEvent: false });
              return;
            }
          }
        } catch {}
        // Can't parse - just don't set coordinates, don't show error
        this.coordError.set(false);
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
    this.latitude.set(point.latitude);
    this.longitude.set(point.longitude);
    this.coordError.set(false);
    this.form.patchValue(
      { coordinates: formatCoordinates(point.latitude, point.longitude) },
      { emitEvent: false }
    );
  }

  clearCoordinates(): void {
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
    try {
      const data = await Promise.all(files.map((file) => {
        if (!file.type.startsWith('image/')) throw new Error('Please choose image files only.');
        if (file.size > 15 * 1024 * 1024) throw new Error('Each photo must be 15 MB or smaller.');
        return this.compressPhoto(file);
      }));
      this.selectedImages.update((images) => [...images, ...data]);
      this.errorMessage.set(null);
    } catch (error) {
      this.errorMessage.set(error instanceof Error ? error.message : 'Could not read selected photos.');
    }
    input.value = '';
  }

  private async compressPhoto(file: File): Promise<string> {
    let bitmap: ImageBitmap;
    try {
      bitmap = await createImageBitmap(file);
    } catch {
      throw new Error('Could not open a selected photo.');
    }
    try {
      const scale = Math.min(1, 1280 / Math.max(bitmap.width, bitmap.height));
      const canvas = document.createElement('canvas');
      canvas.width = Math.max(1, Math.round(bitmap.width * scale));
      canvas.height = Math.max(1, Math.round(bitmap.height * scale));
      const context = canvas.getContext('2d');
      if (!context) throw new Error('Could not process a selected photo.');
      context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
      let quality = 0.72;
      let result = canvas.toDataURL('image/jpeg', quality);
      while (result.length > 100_000 && quality > 0.3) {
        quality -= 0.1;
        result = canvas.toDataURL('image/jpeg', quality);
      }
      if (result.length > 100_000) throw new Error('A photo could not be compressed enough.');
      return result;
    } finally {
      bitmap.close();
    }
  }

  removeSelectedImage(index: number): void {
    this.selectedImages.update((images) => images.filter((_, i) => i !== index));
  }

  removeExistingImage(index: number): void {
    this.existingImages.update((images) => images.filter((_, i) => i !== index));
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
    const imagePayloadSize = payload.images.reduce((size, image) => size + image.length, 0);
    if (imagePayloadSize > 2_000_000) {
      this.errorMessage.set('Photos are too large to submit together. Remove a photo and try again.');
      this.isLoading.set(false);
      return;
    }

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
