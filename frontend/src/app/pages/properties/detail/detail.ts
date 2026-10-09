import { Component, inject, input, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { PropertyService } from '../../../services/property.service';
import { AuthService } from '../../../services/auth.service';
import { ChatService } from '../../../services/chat.service';
import { Property } from '../../../models';
import { IconComponent } from '../../../components/icon/icon';
import { LeafletMapComponent } from '../../../components/leaflet-map/leaflet-map';
import { LanguageService } from '../../../services/language.service';
import { categoryLabel } from '../../../shared/ui';
import { formatCoordinates, googleMapsUrl } from '../../../shared/coords';

@Component({
  selector: 'app-property-detail',
  imports: [CommonModule, ReactiveFormsModule, RouterLink, IconComponent, LeafletMapComponent],
  templateUrl: './detail.html',
})
export class PropertyDetailComponent implements OnInit {
  readonly language = inject(LanguageService);
  readonly id = input.required<string>();

  readonly categoryLabel = categoryLabel;
  readonly formatCoordinates = formatCoordinates;

  activeImage = signal(0);

  mapsUrl(prop: Property): string {
    return googleMapsUrl(prop.latitude!, prop.longitude!);
  }

  selectImage(index: number): void {
    this.activeImage.set(index);
  }

  private readonly propertyService = inject(PropertyService);
  private readonly chat = inject(ChatService);
  readonly auth = inject(AuthService);
  private readonly fb = inject(FormBuilder);
  private readonly router = inject(Router);

  property = signal<Property | null>(null);
  activeBookingId = signal<number | null>(null);
  isLoading = signal(true);
  isFavoritePending = signal(false);
  favoriteError = signal(false);
  isBookingSubmitting = signal(false);
  isMessaging = signal(false);
  messageError = signal(false);
  bookingSuccess = signal<string | null>(null);
  bookingError = signal<string | null>(null);

  bookingForm = this.fb.group({
    move_in_date: ['', [Validators.required]],
    end_date: [''],
    lease_months: [12, [Validators.required, Validators.min(1)]],
    note: [''],
  });

  ngOnInit(): void {
    this.loadDetail();
  }

  loadDetail(): void {
    const propId = Number(this.id());
    if (this.auth.isRenter()) {
      this.propertyService.getRenterProperty(propId).subscribe({
        next: (res) => {
          this.property.set(res.property);
          this.activeBookingId.set(res.active_booking_id);
          this.activeImage.set(0);
          this.isLoading.set(false);
        },
        error: () => this.isLoading.set(false),
      });
    } else {
      this.propertyService.getPublicProperty(propId).subscribe({
        next: (res) => {
          this.property.set(res.property);
          this.activeImage.set(0);
          this.isLoading.set(false);
        },
        error: () => this.isLoading.set(false),
      });
    }
  }

  toggleFavorite(): void {
    const prop = this.property();
    if (!prop || !this.auth.isRenter() || this.isFavoritePending()) return;

    this.isFavoritePending.set(true);
    this.favoriteError.set(false);
    this.propertyService.toggleFavorite(prop.id).subscribe({
      next: (res) => {
        prop.is_favorite = res.favorited;
        prop.favorite_count = res.count;
        this.property.set({ ...prop });
        this.isFavoritePending.set(false);
      },
      error: () => {
        this.isFavoritePending.set(false);
        this.favoriteError.set(true);
      },
    });
  }

  messageLandlord(): void {
    const prop = this.property();
    if (!prop || this.isMessaging()) return;
    this.isMessaging.set(true);
    this.messageError.set(false);
    this.chat.startConversation(prop.id).subscribe({
      next: (res) => {
        this.isMessaging.set(false);
        this.router.navigate(['/messages', res.conversation.id]);
      },
      error: () => {
        this.isMessaging.set(false);
        this.messageError.set(true);
      },
    });
  }

  /** Derive the move-out date from the move-in date + lease duration. */
  recalcEndDate(): void {
    const { move_in_date, lease_months } = this.bookingForm.value;
    const months = Number(lease_months) || 0;
    if (!move_in_date || months <= 0) return;
    const start = new Date(move_in_date);
    if (isNaN(start.getTime())) return;
    start.setMonth(start.getMonth() + months);
    const pad = (n: number) => String(n).padStart(2, '0');
    const iso = `${start.getFullYear()}-${pad(start.getMonth() + 1)}-${pad(start.getDate())}`;
    if (this.bookingForm.get('end_date')?.value !== iso) {
      this.bookingForm.patchValue({ end_date: iso });
    }
  }

  onRequestBooking(): void {
    if (this.bookingForm.invalid) return;
    const prop = this.property();
    if (!prop) return;

    this.isBookingSubmitting.set(true);
    this.bookingError.set(null);
    this.bookingSuccess.set(null);

    const val = this.bookingForm.value;
    this.propertyService
      .requestBooking(prop.id, {
        move_in_date: val.move_in_date || undefined,
        end_date: val.end_date || undefined,
        lease_months: val.lease_months || 12,
        note: val.note || undefined,
      })
      .subscribe({
        next: (res) => {
          this.isBookingSubmitting.set(false);
          this.bookingSuccess.set(`Booking request created (Ref: ${res.reference})`);
          this.activeBookingId.set(res.booking_id);
        },
        error: (err) => {
          this.isBookingSubmitting.set(false);
          const detail = err.error?.detail || '';
          if (detail === 'active_booking_exists') {
            this.bookingError.set('You already have an active booking on this property.');
          } else {
            this.bookingError.set('Failed to submit booking request.');
          }
        },
      });
  }
}
