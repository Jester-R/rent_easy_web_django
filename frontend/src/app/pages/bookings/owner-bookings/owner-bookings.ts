import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { BookingService, BookingListResponse } from '../../../services/booking.service';
import { Booking } from '../../../models';
import { IconComponent } from '../../../components/icon/icon';
import { DataPaginationComponent } from '../../../components/data-pagination/data-pagination';
import { LanguageService } from '../../../services/language.service';
import { propertyLocation, propertyTitle } from '../../../shared/property-text';
import type { Property } from '../../../models';

@Component({
  selector: 'app-owner-bookings',
  imports: [CommonModule, RouterLink, IconComponent, DataPaginationComponent],
  templateUrl: './owner-bookings.html',
})
export class OwnerBookingsComponent implements OnInit {
  readonly language = inject(LanguageService);

  title(property: Property): string {
    return propertyTitle(property, this.language.current());
  }

  location(property: Property): string {
    return propertyLocation(property, this.language.current());
  }
  private readonly bookingService = inject(BookingService);

  bookings = signal<Booking[]>([]);
  counts = signal<Record<string, number>>({});
  total = signal(0);
  page = signal(1);
  readonly pageSize = 25;
  activeTab = signal<string>('all');
  isLoading = signal(true);
  actionMessage = signal<string | null>(null);

  label(value: string): string {
    return this.language.valueLabel(value);
  }

  ngOnInit(): void {
    this.loadBookings();
  }

  loadBookings(status: string = this.activeTab()): void {
    this.isLoading.set(true);
    if (status !== this.activeTab()) this.page.set(1);
    this.activeTab.set(status);
    this.bookingService.getOwnerBookings(status, this.page(), this.pageSize).subscribe({
      next: (res: BookingListResponse) => {
        this.bookings.set(res.bookings);
        this.counts.set(res.counts);
        this.total.set(res.total);
        this.page.set(res.page);
        this.isLoading.set(false);
      },
      error: () => this.isLoading.set(false),
    });
  }

  changePage(page: number): void {
    this.page.set(page);
    this.loadBookings();
  }

  approveBooking(id: number): void {
    this.actionMessage.set(null);
    this.bookingService.approveBooking(id).subscribe({
      next: (res) => {
        this.actionMessage.set(`Booking #${res.booking.reference} approved.`);
        this.loadBookings();
      },
    });
  }

  rejectBooking(id: number): void {
    this.actionMessage.set(null);
    this.bookingService.rejectBooking(id).subscribe({
      next: (res) => {
        this.actionMessage.set(`Booking #${res.booking.reference} rejected.`);
        this.loadBookings();
      },
    });
  }

  cancelBooking(booking: Booking): void {
    const refundMessage = booking.payment_id
      ? '\n\nThe refund request will be sent to the admin team for review.'
      : '';
    if (!confirm(`Cancel booking #${booking.reference}?${refundMessage}`)) return;
    this.actionMessage.set(null);
    this.bookingService.ownerCancelBooking(booking.id).subscribe({
      next: (res) => {
        this.actionMessage.set(`Booking #${res.booking.reference} cancelled.`);
        this.loadBookings();
      },
    });
  }
}
