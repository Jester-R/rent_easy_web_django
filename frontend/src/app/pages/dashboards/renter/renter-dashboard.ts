import { Component, inject, OnInit, PLATFORM_ID, signal } from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { RouterLink } from '@angular/router';
import { AuthService } from '../../../services/auth.service';
import { RenterDashboardData } from '../../../models';
import { PropertyCardComponent } from '../../../components/property-card/property-card';
import { LanguageService } from '../../../services/language.service';

@Component({
  selector: 'app-renter-dashboard',
  imports: [CommonModule, RouterLink, PropertyCardComponent],
  templateUrl: './renter-dashboard.html',
})
export class RenterDashboardComponent implements OnInit {
  readonly language = inject(LanguageService);
  readonly auth = inject(AuthService);
  private readonly platformId = inject(PLATFORM_ID);

  data = signal<RenterDashboardData | null>(null);
  isLoading = signal(true);
  hasError = signal(false);

  ngOnInit(): void {
    // /rent/ is both this page's route and the renter dashboard API endpoint.
    // A server-side request resolves back to this SSR route and never settles.
    if (!isPlatformBrowser(this.platformId)) return;

    this.loadDashboard();
  }

  loadDashboard(): void {
    this.isLoading.set(true);
    this.hasError.set(false);
    this.auth.getRenterDashboard().subscribe({
      next: (res) => {
        this.data.set(res);
        this.isLoading.set(false);
      },
      error: () => {
        this.isLoading.set(false);
        this.hasError.set(true);
      },
    });
  }
}
