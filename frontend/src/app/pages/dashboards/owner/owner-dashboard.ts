import { Component, inject, OnInit, PLATFORM_ID, signal } from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { RouterLink } from '@angular/router';
import { AuthService } from '../../../services/auth.service';
import { OwnerDashboardData } from '../../../models';

@Component({
  selector: 'app-owner-dashboard',
  imports: [CommonModule, RouterLink],
  templateUrl: './owner-dashboard.html',
})
export class OwnerDashboardComponent implements OnInit {
  readonly auth = inject(AuthService);
  private readonly platformId = inject(PLATFORM_ID);

  data = signal<OwnerDashboardData | null>(null);
  isLoading = signal(true);
  hasError = signal(false);

  ngOnInit(): void {
    // /owner/ is both this page's route and the dashboard API endpoint. During
    // SSR, requesting it from HttpClient recursively renders this page.
    if (!isPlatformBrowser(this.platformId)) return;

    this.loadDashboard();
  }

  loadDashboard(): void {
    this.isLoading.set(true);
    this.hasError.set(false);
    this.auth.getOwnerDashboard().subscribe({
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
