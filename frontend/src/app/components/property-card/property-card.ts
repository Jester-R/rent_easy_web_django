import { Component, input, output, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { Property } from '../../models';
import { PropertyService } from '../../services/property.service';
import { AuthService } from '../../services/auth.service';
import { categoryLabel } from '../../shared/ui';

@Component({
  selector: 'app-property-card',
  imports: [CommonModule, RouterLink],
  templateUrl: './property-card.html',
})
export class PropertyCardComponent {
  readonly property = input.required<Property>();
  readonly favoriteToggled = output<{ propertyId: number; favorited: boolean }>();

  readonly categoryLabel = categoryLabel;

  private readonly propertyService = inject(PropertyService);
  readonly auth = inject(AuthService);
  readonly favoritePending = signal(false);
  readonly favoriteError = signal(false);

  get locationLabel(): string {
    return this.property().location
      .replace(/_/g, ' ')
      .replace(/\b(Phnom Penh)(?:\s+Phnom Penh|\s+Penh)+\b/gi, '$1')
      .trim();
  }

  toggleFavorite(event: Event): void {
    event.preventDefault();
    event.stopPropagation();
    if (this.favoritePending()) return;

    const prop = this.property();
    this.favoritePending.set(true);
    this.favoriteError.set(false);
    this.propertyService.toggleFavorite(prop.id).subscribe({
      next: (res) => {
        prop.is_favorite = res.favorited;
        prop.favorite_count = res.count;
        this.favoritePending.set(false);
        this.favoriteToggled.emit({ propertyId: prop.id, favorited: res.favorited });
      },
      error: () => {
        this.favoritePending.set(false);
        this.favoriteError.set(true);
      },
    });
  }
}
