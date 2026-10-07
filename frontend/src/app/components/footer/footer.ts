import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-footer',
  imports: [RouterLink],
  template: `
    <footer class="border-t border-hairline bg-surface py-10 text-ink-2">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="mb-8 grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-4">
          <div class="space-y-4">
            <div class="flex items-center gap-2">
              <div class="hero-gradient flex h-8 w-8 items-center justify-center rounded-lg text-sm font-bold text-white">RE</div>
              <span class="text-lg font-bold text-ink">RentEasy</span>
            </div>
            <p class="text-xs leading-relaxed text-ink-3">
              Modern property rental ecosystem connecting verified owners with quality tenants across Cambodia and beyond.
            </p>
          </div>

          <div>
            <h4 class="mb-3 text-xs font-semibold uppercase tracking-wider text-ink">Explore</h4>
            <ul class="space-y-2 text-xs">
              <li><a routerLink="/browse" class="transition-colors hover:text-primary">Browse Listings</a></li>
              <li><a routerLink="/login" class="transition-colors hover:text-primary">Tenant Portal</a></li>
              <li><a routerLink="/login" class="transition-colors hover:text-primary">Owner Dashboard</a></li>
            </ul>
          </div>

          <div>
            <h4 class="mb-3 text-xs font-semibold uppercase tracking-wider text-ink">Company</h4>
            <ul class="space-y-2 text-xs">
              <li><a href="#" class="transition-colors hover:text-primary">About RentEasy</a></li>
              <li><a href="#" class="transition-colors hover:text-primary">Terms of Service</a></li>
              <li><a href="#" class="transition-colors hover:text-primary">Privacy Policy</a></li>
            </ul>
          </div>

          <div>
            <h4 class="mb-3 text-xs font-semibold uppercase tracking-wider text-ink">Security & Trust</h4>
            <p class="text-xs leading-relaxed text-ink-3">
              Verified landlords, secure payment tracking, automated lease agreements, and transparent booking fees.
            </p>
          </div>
        </div>

        <div class="flex flex-col items-center justify-between gap-2 border-t border-hairline pt-6 text-xs text-ink-3 sm:flex-row">
          <p>&copy; 2026 RentEasy Web Platform. All rights reserved.</p>
          <p>Powered by Django & Angular</p>
        </div>
      </div>
    </footer>
  `,
})
export class FooterComponent {}
