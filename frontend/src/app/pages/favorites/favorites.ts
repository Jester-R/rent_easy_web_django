import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { PropertyService } from '../../services/property.service';
import { Property } from '../../models';
import { PropertyCardComponent } from '../../components/property-card/property-card';
import { IconComponent } from '../../components/icon/icon';
import { DataPaginationComponent } from '../../components/data-pagination/data-pagination';
import { LanguageService } from '../../services/language.service';

@Component({
  selector: 'app-renter-favorites',
  imports: [CommonModule, RouterLink, PropertyCardComponent, IconComponent, DataPaginationComponent],
  templateUrl: './favorites.html',
})
export class RenterFavoritesComponent implements OnInit {
  readonly language = inject(LanguageService);
  private readonly propertyService = inject(PropertyService);

  favorites = signal<Property[]>([]);
  total = signal(0);
  page = signal(1);
  readonly pageSize = 24;
  isLoading = signal(true);

  ngOnInit(): void {
    this.loadFavorites();
  }

  loadFavorites(): void {
    this.isLoading.set(true);
    this.propertyService.getFavorites(this.page(), this.pageSize).subscribe({
      next: (res) => {
        this.favorites.set(res.favorites);
        this.total.set(res.total);
        this.page.set(res.page);
        this.isLoading.set(false);
      },
      error: () => this.isLoading.set(false),
    });
  }

  changePage(page: number): void {
    this.page.set(page);
    this.loadFavorites();
  }

  onFavoriteToggled(event: { propertyId: number; favorited: boolean }): void {
    if (!event.favorited) {
      this.favorites.update((list) => list.filter((p) => p.id !== event.propertyId));
    }
  }
}
