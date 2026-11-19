import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Router, RouterLink } from '@angular/router';
import { BookingService, BookingListResponse } from '../../../services/booking.service';
import { ChatService } from '../../../services/chat.service';
import { Booking } from '../../../models';
import { IconComponent } from '../../../components/icon/icon';
import { DataPaginationComponent } from '../../../components/data-pagination/data-pagination';
import { LanguageService } from '../../../services/language.service';
import { propertyLocation, propertyTitle } from '../../../shared/property-text';
import type { Property } from '../../../models';
import { bookingPill } from '../../../shared/ui';

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
  private readonly chat = inject(ChatService);
  private readonly router = inject(Router);

  bookings = signal<Booking[]>([]);
  counts = signal<Record<string, number>>({});
  total = signal(0);
  page = signal(1);
  readonly pageSize = 25;
  activeTab = signal<string>('all');
  isLoading = signal(true);
  actionMessage = signal<string | null>(null);
  isOpeningChatId = signal<number | null>(null);
  isOpeningRenterChatId = signal<number | null>(null);
  chatError = signal<string | null>(null);

  label(value: string): string {
    return this.language.valueLabel(value);
  }

  refundStatePill(state: string): string {
    if (state === 'Refunded') return 'pill-refunded';
    if (state === 'Refund failed') return 'pill-rejected';
    return 'pill-pending';
  }

  bookingState(b: Booking): { label: string; pill: string } {
    const status = this.label(b.status);
    if (b.refund_state) {
      return {
        label: this.label(b.refund_state),
        pill: this.refundStatePill(b.refund_state),
      };
    }
    if (b.is_paid && b.status !== 'Confirmed') {
      return {
        label: `${status} · ${this.language.t('ownerBookings.paid')}`,
        pill: bookingPill(b.status),
      };
    }
    return { label: status, pill: bookingPill(b.status) };
  }

  openRenterChat(b: Booking): void {
    if (this.isOpeningRenterChatId() !== null) return;
    this.chatError.set(null);
    this.isOpeningRenterChatId.set(b.id);
    this.chat.openBookingChat(b.id).subscribe({
      next: (res) => {
        this.isOpeningRenterChatId.set(null);
        void this.router.navigateByUrl(`/messages/${res.conversation.id}`);
      },
      error: (err: HttpErrorResponse) => {
        this.isOpeningRenterChatId.set(null);
        this.chatError.set(
          err.error?.detail || this.language.t('ownerBookings.renterChatUnavailable')
        );
      },
    });
  }

  canOpenRefundChat(b: Booking): boolean {
    return !!b.refund_id && ['Accepted', 'Processed'].includes(b.refund_status || '');
  }

  openRefundChat(b: Booking): void {
    if (!b.refund_id || !this.canOpenRefundChat(b) || this.isOpeningChatId() !== null) return;
    this.chatError.set(null);
    this.isOpeningChatId.set(b.id);
    this.chat.openRefundChat(b.refund_id).subscribe({
      next: (res) => {
        this.isOpeningChatId.set(null);
        void this.router.navigateByUrl(res.url);
      },
      error: (err: HttpErrorResponse) => {
        this.isOpeningChatId.set(null);
        this.chatError.set(
          err.error?.detail || this.language.t('ownerBookings.refundChatUnavailable')
        );
      },
    });
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

  cancelBooking(booking: Booking): void {
    const message = window.prompt(
      this.language.t('ownerBookings.refundMessagePrompt'),
      ''
    );
    if (message === null) return;
    if (!message.trim()) {
      alert(this.language.t('ownerBookings.refundMessageRequired'));
      return;
    }
    this.actionMessage.set(null);
    this.bookingService.ownerCancelBooking(booking.id, message).subscribe({
      next: (res) => {
        this.actionMessage.set(`Booking #${res.booking.reference} cancelled.`);
        this.loadBookings();
      },
    });
  }
}
