import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { BookingService, BookingListResponse } from '../../../services/booking.service';
import { Booking } from '../../../models';
import { IconComponent } from '../../../components/icon/icon';
import { LanguageService } from '../../../services/language.service';

@Component({
  selector: 'app-owner-bookings',
  imports: [CommonModule, RouterLink, IconComponent],
  templateUrl: './owner-bookings.html',
})
export class OwnerBookingsComponent implements OnInit {
  readonly language = inject(LanguageService);
  private readonly bookingService = inject(BookingService);

  bookings = signal<Booking[]>([]);
  counts = signal<Record<string, number>>({});
  activeTab = signal<string>('all');
  isLoading = signal(true);
  actionMessage = signal<string | null>(null);

  label(value: string): string {
    const khmer: Record<string, string> = {
      all: 'ទាំងអស់', Pending: 'កំពុងរង់ចាំ', Approved: 'បានអនុម័ត',
      Confirmed: 'បានបញ្ជាក់', Rejected: 'បានបដិសេធ', Cancelled: 'បានលុបចោល',
    };
    return this.language.current() === 'km' ? (khmer[value] ?? value) : value;
  }

  ngOnInit(): void {
    this.loadBookings();
  }

  loadBookings(status: string = this.activeTab()): void {
    this.isLoading.set(true);
    this.activeTab.set(status);
    this.bookingService.getOwnerBookings(status).subscribe({
      next: (res: BookingListResponse) => {
        this.bookings.set(res.bookings);
        this.counts.set(res.counts);
        this.isLoading.set(false);
      },
      error: () => this.isLoading.set(false),
    });
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
}
