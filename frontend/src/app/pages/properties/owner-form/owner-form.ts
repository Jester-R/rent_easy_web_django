import { Component, inject, input, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { PropertyService } from '../../../services/property.service';
import { LanguageService } from '../../../services/language.service';
import { LeafletMapComponent } from '../../../components/leaflet-map/leaflet-map';
import {
  SearchableSelectComponent,
  SelectOption,
} from '../../../components/searchable-select/searchable-select';
import { PROPERTY_CATEGORIES } from '../../../shared/ui';
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

  readonly categories = PROPERTY_CATEGORIES;

  readonly categoryOptions: SelectOption[] = [
    { value: '', label: this.language.t('Uncategorized', 'មិនបានចាត់ថ្នាក់') },
    ...PROPERTY_CATEGORIES.map((cat) => ({ value: cat.value, label: cat.label })),
  ];

  private readonly fb = inject(FormBuilder);
  private readonly propertyService = inject(PropertyService);
  private readonly router = inject(Router);

  isEdit = signal(false);
  isLoading = signal(false);
  errorMessage = signal<string | null>(null);

  latitude = signal<number | null>(null);
  longitude = signal<number | null>(null);
  coordError = signal(false);

  form = this.fb.group({
    title: ['', [Validators.required]],
    location: ['', [Validators.required]],
    price_per_month: [500, [Validators.required, Validators.min(1)]],
    category: [''],
    bedrooms: [1, [Validators.required, Validators.min(0)]],
    bathrooms: [1, [Validators.required, Validators.min(0)]],
    description: [''],
    coordinates: [''],
    images_text: [''],
  });

  ngOnInit(): void {
    const editId = this.id();
    if (editId) {
      this.isEdit.set(true);
      this.loadProperty(Number(editId));
    }
  }

  loadProperty(id: number): void {
    this.isLoading.set(true);
    this.propertyService.getPublicProperty(id).subscribe({
      next: (res) => {
        this.isLoading.set(false);
        const p = res.property;
        this.form.patchValue({
          title: p.title,
          location: p.location,
          price_per_month: p.price_per_month,
          category: p.category || '',
          bedrooms: p.bedrooms,
          bathrooms: p.bathrooms,
          description: p.description,
          coordinates: formatCoordinates(p.latitude, p.longitude),
          images_text: (p.images || []).join('\n'),
        });
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
    } else if (raw.trim()) {
      this.coordError.set(true);
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

  private imageList(): string[] {
    const raw = this.form.get('images_text')?.value || '';
    return raw
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean)
      .slice(0, 12);
  }

  onSubmit(): void {
    if (this.form.invalid) return;

    this.isLoading.set(true);
    this.errorMessage.set(null);

    const val = this.form.value;
    const payload = {
      title: val.title || '',
      location: val.location || '',
      price_per_month: Number(val.price_per_month) || 0,
      category: val.category || '',
      bedrooms: Number(val.bedrooms) || 0,
      bathrooms: Number(val.bathrooms) || 0,
      description: val.description || '',
      latitude: this.latitude(),
      longitude: this.longitude(),
      images: this.imageList(),
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
          this.errorMessage.set(err.error?.detail || 'Failed to create property.');
        },
      });
    }
  }
}
