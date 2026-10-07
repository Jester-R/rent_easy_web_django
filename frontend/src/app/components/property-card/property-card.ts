import { Component, input, output, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { Property } from '../../models';
import { PropertyService } from '../../services/property.service';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-property-card',
  imports: [CommonModule, RouterLink],
  templateUrl: './property-card.html',
})
export class PropertyCardComponent {
  readonly property = input.required<Property>();
  readonly favoriteToggled = output<{ propertyId: number; favorited: boolean }>();

  private readonly propertyService = inject(PropertyService);
  readonly auth = inject(AuthService);

  toggleFavorite(event: Event): void {
    event.preventDefault();
    event.stopPropagation();
    const prop = this.property();
    this.propertyService.toggleFavorite(prop.id).subscribe({
      next: (res) => {
        prop.is_favorite = res.favorited;
        this.favoriteToggled.emit({ propertyId: prop.id, favorited: res.favorited });
      },
    });
  }
}
