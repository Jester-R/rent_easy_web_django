import { Component, effect, inject, input, OnDestroy, OnInit, signal } from '@angular/core';
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
import { PropertyCategoryService } from '../../../services/property-category.service';
import { formatCoordinates } from '../../../shared/coords';
import { formatReservationCountdown } from '../../../shared/reservation-countdown';
import { propertyDescription, propertyLocation, propertyTitle } from '../../../shared/property-text';

@Component({
  selector: 'app-property-detail',
  imports: [CommonModule, ReactiveFormsModule, RouterLink, IconComponent, LeafletMapComponent],
  templateUrl: './detail.html',
})
export class PropertyDetailComponent implements OnInit, OnDestroy {
  readonly language = inject(LanguageService);
  readonly id = input.required<string>();

  readonly formatCoordinates = formatCoordinates;

  activeImage = signal(0);

  titleLabel(prop: Property): string {
    return propertyTitle(prop, this.language.current());
  }

  locationLabel(prop: Property): string {
    return propertyLocation(prop, this.language.current());
  }

  descriptionLabel(prop: Property): string {
    return propertyDescription(prop, this.language.current());
  }

  googleMapsUrl(prop: Property): string {
    const lat = prop.latitude;
    const lng = prop.longitude;
    const query =
      typeof lat === 'number' && typeof lng === 'number'
        ? `${lat},${lng}`
        : this.locationLabel(prop).trim();
    return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query)}`;
  }

  reservationCountdown(value: string | null | undefined): string | null {
    return formatReservationCountdown(value, this.now());
  }

  private startReservationTimer(): void {
    if (this.reservationTimer) return;
    this.reservationTimer = setInterval(() => {
      this.now.set(Date.now());
      this.refreshExpiredReservation();
    }, 1000);
  }

  private refreshExpiredReservation(): void {
    const prop = this.property();
    const deadline =
      prop?.rebook_available_at
      ?? (prop?.booked_by_other ? prop.reservation_expires_at : null);
    if (!deadline) return;

    const expiresAt = Date.parse(deadline);
    if (!Number.isFinite(expiresAt) || Date.now() < expiresAt) return;
    if (this.lastExpiredDeadline === deadline) return;

    this.lastExpiredDeadline = deadline;
    this.loadDetail();
  }

  selectImage(index: number): void {
    this.activeImage.set(index);
  }

  private readonly propertyService = inject(PropertyService);
  private readonly categories = inject(PropertyCategoryService);
  private readonly chat = inject(ChatService);
  readonly auth = inject(AuthService);
  private readonly fb = inject(FormBuilder);
  private readonly router = inject(Router);

  private reservationTimer: ReturnType<typeof setInterval> | null = null;
  private lastExpiredDeadline: string | null = null;
  readonly now = signal(Date.now());

  property = signal<Property | null>(null);
  ownerStatus = signal<string>('available');
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
    lease_months: [
      '1',
      [
        Validators.required,
        Validators.min(1),
        Validators.max(60),
        Validators.pattern(/^\d+$/),
      ],
    ],
    note: [''],
  });

  categoryLabel(value?: string | null): string {
    return this.categories.label(value, this.language.current());
  }

  constructor() {
    // Auth state resolves asynchronously. Loading before it settles would use
    // the public endpoint, which has no reservation flags and would show the
    // lease form to other renters.
    effect(() => {
      if (this.auth.isLoading()) return;
      this.loadDetail();
    });
  }

  ngOnInit(): void {
    this.startReservationTimer();
  }

  ngOnDestroy(): void {
    if (this.reservationTimer) {
      clearInterval(this.reservationTimer);
      this.reservationTimer = null;
    }
  }

  loadDetail(): void {
    const propId = Number(this.id());
    if (!Number.isSafeInteger(propId) || propId <= 0) {
      this.isLoading.set(false);
      return;
    }
    if (this.auth.isRenter()) {
      this.propertyService.getRenterProperty(propId).subscribe({
        next: (res) => {
          const bookedByOther =
            res.booked_by_other ?? Boolean(res.property.booked_by_other);
          const rebookAt =
            res.rebook_available_at ?? res.property.rebook_available_at ?? null;
          this.property.set({
            ...res.property,
            has_active_booking:
              res.has_active_booking || Boolean(res.active_booking_id),
            booked_by_other: bookedByOther,
            reservation_expires_at:
              res.reservation_expires_at ?? res.property.reservation_expires_at,
            booking_status: res.booking_status ?? res.property.booking_status ?? null,
            rebook_available_at: rebookAt,
          });
          if (!bookedByOther && !rebookAt) this.lastExpiredDeadline = null;
          this.ownerStatus.set(res.owner_status || res.property.owner_status || 'available');
          this.activeImage.set(0);
          this.isLoading.set(false);
        },
        error: () => this.loadPublicDetail(propId),
      });
      return;
    }
    this.loadPublicDetail(propId);
  }

  private loadPublicDetail(propId: number): void {
    this.propertyService.getPublicProperty(propId).subscribe({
      next: (res) => {
        this.property.set({
          ...res.property,
          is_favorite: res.is_favorite,
        });
        this.lastExpiredDeadline = null;
        this.ownerStatus.set(res.property.owner_status || 'available');
        this.activeImage.set(0);
        this.isLoading.set(false);
      },
      error: () => this.isLoading.set(false),
    });
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

  onLeaseMonthsInput(event: Event): void {
    const input = event.target as HTMLInputElement;
    const cleaned = input.value.replace(/\D/g, '');
    if (cleaned !== input.value) {
      input.value = cleaned;
    }
    this.bookingForm.get('lease_months')?.setValue(cleaned || null);
    this.recalcEndDate();
  }

  onLeaseMonthsKeydown(event: KeyboardEvent): void {
    if (event.ctrlKey || event.metaKey || event.altKey) return;
    if (event.key.length === 1 && !/^\d$/.test(event.key)) {
      event.preventDefault();
    }
  }

  onLeaseMonthsPaste(event: ClipboardEvent): void {
    const text = event.clipboardData?.getData('text') ?? '';
    if (/\D/.test(text)) {
      event.preventDefault();
    }
  }

  /** Derive the move-out date from the move-in date + lease duration. */
  recalcEndDate(): void {
    const { move_in_date, lease_months } = this.bookingForm.value;
    const months = Number(lease_months);
    if (!move_in_date || !Number.isInteger(months) || months < 1) return;
    const [year, month, day] = move_in_date.split('-').map(Number);
    if (!year || !month || !day) return;
    const targetMonth = month - 1 + months;
    const targetYear = year + Math.floor(targetMonth / 12);
    const normalizedMonth = ((targetMonth % 12) + 12) % 12;
    const lastDay = new Date(targetYear, normalizedMonth + 1, 0).getDate();
    const moveOutDay = Math.min(day, lastDay);
    const endDate = new Date(targetYear, normalizedMonth, moveOutDay);
    const pad = (n: number) => String(n).padStart(2, '0');
    const iso = `${endDate.getFullYear()}-${pad(endDate.getMonth() + 1)}-${pad(endDate.getDate())}`;
    if (this.bookingForm.get('end_date')?.value !== iso) {
      this.bookingForm.patchValue({ end_date: iso });
    }
  }

  onRequestBooking(): void {
    if (this.bookingForm.get("lease_months")?.invalid) {
      this.bookingError.set(this.language.t('propertyDetail.leaseDurationWholeNumber'));
      return;
    }
    if (this.bookingForm.invalid) return;
    const prop = this.property();
    if (!prop || prop.booked_by_other || prop.has_paid_booking) {
      this.bookingError.set(this.language.t('propertyDetail.bookedBySomeoneElse'));
      return;
    }
    if (prop.rebook_available_at) {
      this.bookingError.set(this.language.t('propertyDetail.cancelledWaitActive'));
      return;
    }

    this.isBookingSubmitting.set(true);
    this.bookingError.set(null);
    this.bookingSuccess.set(null);

    const val = this.bookingForm.value;
    const months = Number(String(val.lease_months ?? '').replace(/\D/g, ''));
    this.propertyService
      .requestBooking(prop.id, {
        move_in_date: val.move_in_date || undefined,
        end_date: val.end_date || undefined,
        lease_months: months,
        note: val.note || undefined,
      })
      .subscribe({
        next: (res) => {
          this.isBookingSubmitting.set(false);
          this.bookingSuccess.set(`Booking request created (Ref: ${res.reference})`);
          this.property.update((prop) =>
            prop ? { ...prop, has_active_booking: true } : prop,
          );
        },
        error: (err) => {
          this.isBookingSubmitting.set(false);
          const detail = err.error?.detail || '';
          if (detail === 'booking_unavailable_or_already_booked_today') {
            this.bookingError.set(
              'This room is unavailable, or you requested it within the last 24 hours. You can try another room.',
            );
          } else {
            this.bookingError.set('Failed to submit booking request.');
          }
        },
      });
  }
}
