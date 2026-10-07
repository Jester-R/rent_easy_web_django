import { Component, inject, OnInit, PLATFORM_ID, signal } from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { RouterLink } from '@angular/router';
import { PropertyService } from '../../services/property.service';
import { AuthService } from '../../services/auth.service';
import { LandingData } from '../../models';
import { PropertyCardComponent } from '../../components/property-card/property-card';

@Component({
  selector: 'app-landing',
  imports: [CommonModule, RouterLink, PropertyCardComponent],
  templateUrl: './landing.html',
})
export class LandingComponent implements OnInit {
  private readonly propertyService = inject(PropertyService);
  private readonly platformId = inject(PLATFORM_ID);
  readonly auth = inject(AuthService);

  landingData = signal<LandingData | null>(null);
  isLoading = signal(true);

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
