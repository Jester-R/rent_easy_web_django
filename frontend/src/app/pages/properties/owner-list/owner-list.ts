import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { DataPaginationComponent } from '../../../components/data-pagination/data-pagination';
import { RouterLink } from '@angular/router';
import { PropertyService } from '../../../services/property.service';
import { Property } from '../../../models';
import { LanguageService } from '../../../services/language.service';
import { propertyDescription, propertyLocation, propertyTitle } from '../../../shared/property-text';

@Component({
  selector: 'app-owner-properties',
  imports: [CommonModule, RouterLink, DataPaginationComponent],
  templateUrl: './owner-list.html',
})
export class OwnerPropertiesComponent implements OnInit {
  readonly language = inject(LanguageService);
  private readonly propertyService = inject(PropertyService);

  properties = signal<Property[]>([]);
  total = signal(0);
  page = signal(1);
  readonly pageSize = 25;
  isLoading = signal(true);
  successMessage = signal<string | null>(null);

  title(p: Property): string {
    return propertyTitle(p, this.language.current());
  }

  location(p: Property): string {
    return propertyLocation(p, this.language.current());
  }

  description(p: Property): string {
    return propertyDescription(p, this.language.current());
  }

  ngOnInit(): void {
    this.loadProperties();
  }

  loadProperties(): void {
    this.isLoading.set(true);
    this.propertyService.getOwnerProperties(this.page(), this.pageSize).subscribe({
      next: (res) => {
        this.properties.set(res.properties);
        this.total.set(res.total);
        this.page.set(res.page);
        this.isLoading.set(false);
      },
      error: () => this.isLoading.set(false),
    });
  }

  changePage(page: number): void {
    this.page.set(page);
    this.loadProperties();
  }

  deleteProperty(id: number): void {
    if (!confirm(this.language.t('ownerList.deleteConfirm'))) return;

    this.propertyService.deleteProperty(id).subscribe({
      next: (res) => {
        this.successMessage.set(
          res.refunds_requested
            ? `Listing hidden. ${res.refunds_requested} paid booking(s) sent to the admin team for refund review.`
            : 'Listing hidden from public browsing.'
        );
        this.loadProperties();
      },
      error: (err: HttpErrorResponse) => this.successMessage.set(this.errorMessage(err)),
    });
  }

  toggleAvailability(p: Property): void {
    const unavailable = p.owner_status !== 'unavailable';
    const confirmKey = unavailable ? 'unavailableConfirm' : 'availableConfirm';
    if (!confirm(this.language.t(`ownerList.${confirmKey}`))) return;

    this.propertyService.setAvailability(p.id, unavailable).subscribe({
      next: () => {
        this.successMessage.set(this.language.t('ownerList.availabilityUpdated'));
        this.loadProperties();
      },
      error: (err: HttpErrorResponse) => this.successMessage.set(this.errorMessage(err)),
    });
  }

  private errorMessage(err: HttpErrorResponse): string {
    const detail = err.error?.detail;
    if (detail === 'owner_action_rate_limited') {
      return this.language.t('ownerList.rateLimited');
    }
    if (detail === 'active_paid_booking') {
      return this.language.t('ownerList.activePaidBooking');
    }
    if (detail === 'availability_not_changed') {
      return this.language.t('ownerList.actionFailed');
    }
    return detail || this.language.t('ownerList.actionFailed');
  }

  reopenProperty(id: number): void {
    if (!confirm(this.language.t('ownerList.reopenConfirm'))) return;
    this.propertyService.reopenProperty(id).subscribe({
      next: () => {
        this.successMessage.set(this.language.t('ownerList.reopenListing'));
        this.loadProperties();
      },
    });
  }
}
