import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
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
    if (!confirm('Remove this listing from public browsing? Any active paid bookings will be sent to the admin team for review before a refund is issued.')) return;

    this.propertyService.deleteProperty(id).subscribe({
      next: (res) => {
        this.successMessage.set(
          res.refunds_requested
            ? `Listing hidden. ${res.refunds_requested} paid booking(s) sent to the admin team for refund review.`
            : 'Listing hidden from public browsing.'
        );
        this.loadProperties();
      },
    });
  }
}
