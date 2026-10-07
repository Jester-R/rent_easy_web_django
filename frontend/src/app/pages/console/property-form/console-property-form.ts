import { Component, inject, input, OnInit, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { IconComponent } from '../../../components/icon/icon';
import { ConsoleService } from '../../../services/console.service';
import { PropertyService } from '../../../services/property.service';
import { Property, User } from '../../../models';
import { prettyDate } from '../../../shared/ui';

@Component({
  selector: 'app-console-property-form',
  imports: [ReactiveFormsModule, RouterLink, IconComponent],
  templateUrl: './console-property-form.html',
})
export class ConsolePropertyFormComponent implements OnInit {
  readonly id = input<string>();

  private readonly fb = inject(FormBuilder);
  private readonly console = inject(ConsoleService);
  private readonly propertyService = inject(PropertyService);
  private readonly router = inject(Router);

  readonly prettyDate = prettyDate;

  isEdit = signal(false);
  isLoading = signal(true);
  isSaving = signal(false);
  submitted = signal(false);
  errorMessage = signal<string | null>(null);
  property = signal<Property | null>(null);
  owners = signal<User[]>([]);

  form = this.fb.group({
    title: ['', [Validators.required, Validators.maxLength(160)]],
    location: ['', [Validators.required, Validators.maxLength(160)]],
    owner: [null as number | null, [Validators.required]],
    price_per_month: [null as number | null, [Validators.required, Validators.min(0)]],
    bedrooms: [2, [Validators.required, Validators.min(0), Validators.max(99)]],
    bathrooms: [1, [Validators.required, Validators.min(0), Validators.max(99)]],
    description: ['', [Validators.required]],
  });

  ngOnInit(): void {
    this.loadOwners();
    const editId = this.id();
    if (editId) {
      this.isEdit.set(true);
      this.loadProperty(Number(editId));
    } else {
      this.isLoading.set(false);
    }
  }

  loadOwners(): void {
    this.console.getUsers({ role: 'owner' }).subscribe({
      next: (res) => this.owners.set(res.users),
    });
  }

  loadProperty(id: number): void {
    this.isLoading.set(true);
    this.propertyService.getPublicProperty(id).subscribe({
      next: (res) => {
        this.isLoading.set(false);
        this.property.set(res.property);
        this.form.patchValue({
          title: res.property.title,
          location: res.property.location,
          owner: res.property.owner_id,
          price_per_month: res.property.price_per_month,
          bedrooms: res.property.bedrooms,
          bathrooms: res.property.bathrooms,
          description: res.property.description,
        });
      },
      error: (err) => {
        this.isLoading.set(false);
        this.errorMessage.set(this.friendlyError(err, 'Failed to load property.'));
      },
    });
  }

  showError(name: string): boolean {
    const control = this.form.get(name);
    return !!control && control.invalid && (control.touched || control.dirty || this.submitted());
  }

  onSubmit(): void {
    this.submitted.set(true);
    this.errorMessage.set(null);
    if (this.form.invalid) return;

    this.isSaving.set(true);
    const value = this.form.value;
    const payload: Record<string, unknown> = {
      title: value.title || '',
      location: value.location || '',
      owner: Number(value.owner),
      price_per_month: Number(value.price_per_month) || 0,
      bedrooms: Number(value.bedrooms) || 0,
      bathrooms: Number(value.bathrooms) || 0,
      description: value.description || '',
    };

    const editId = this.id();
    const request = editId
      ? this.console.updateProperty(Number(editId), payload)
      : this.console.createProperty(payload);

    request.subscribe({
      next: () => {
        this.isSaving.set(false);
        this.router.navigate(['/console/properties']);
      },
      error: (err) => {
        this.isSaving.set(false);
        this.errorMessage.set(this.friendlyError(err, 'Failed to save property.'));
      },
    });
  }

  private friendlyError(err: unknown, fallback: string): string {
    const detail = (err as { error?: { detail?: string } }).error?.detail;
    if (!detail) return fallback;
    const messages: Record<string, string> = {
      email_taken: 'Email or username already in use',
      password_too_short: 'Password must be at least 6 characters.',
      username_invalid: 'Username must be 3-30 characters using letters, numbers, ., _ or -',
      title_required: 'Title is required',
      location_required: 'Location is required',
      price_required: 'Enter a valid price',
      owner_required: 'Select an owner with the Property Owner role.',
    };
    return messages[detail] || detail;
  }
}