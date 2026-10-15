import { Component, inject, OnInit, PLATFORM_ID, signal } from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { RouterLink } from '@angular/router';
import { PropertyService } from '../../services/property.service';
import { AuthService } from '../../services/auth.service';
import { LandingData } from '../../models';
import { PropertyCardComponent } from '../../components/property-card/property-card';
import { LanguageService } from '../../services/language.service';
import { propertyLocation, propertyTitle } from '../../shared/property-text';
import type { Property } from '../../models';

@Component({
  selector: 'app-landing',
  imports: [CommonModule, RouterLink, PropertyCardComponent],
  templateUrl: './landing.html',
})
export class LandingComponent implements OnInit {
  private readonly propertyService = inject(PropertyService);
  private readonly platformId = inject(PLATFORM_ID);
  readonly auth = inject(AuthService);
  readonly language = inject(LanguageService);

  landingData = signal<LandingData | null>(null);
  isLoading = signal(true);

  title(property: Property): string {
    return propertyTitle(property, this.language.current());
  }

  location(property: Property): string {
    return propertyLocation(property, this.language.current());
  }

  promotionText(field: 'eyebrow' | 'title' | 'body'): string {
    const language = this.language.current();
    const key = `landing.homePromotion${field[0].toUpperCase()}${field.slice(1)}`;
    const custom = this.landingData()?.home_promotion?.[`${field}_${language}`];
    return custom?.trim() || this.language.t(key);
  }

  ngOnInit(): void {
    // Load the API data in the browser. The static landing content can render
    // on the server without making SSR wait on a same-origin API request.
    if (!isPlatformBrowser(this.platformId)) {
      this.isLoading.set(false);
      return;
    }

    this.propertyService.getLandingData().subscribe({
      next: (data) => {
        this.landingData.set(data);
        this.isLoading.set(false);
      },
      error: () => {
        this.isLoading.set(false);
      },
    });
  }
}
