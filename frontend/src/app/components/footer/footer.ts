import { Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { LanguageService } from '../../services/language.service';

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
              {{ language.t('footer.modernPropertyRentalEcosystemConnectingVerified') }}
            </p>
          </div>

          <div>
            <h4 class="mb-3 text-xs font-semibold uppercase tracking-wider text-ink">{{ language.t('footer.explore') }}</h4>
            <ul class="space-y-2 text-xs">
              <li><a routerLink="/browse" class="transition-colors hover:text-primary">{{ language.t('footer.browseListings') }}</a></li>
              <li><a routerLink="/login" class="transition-colors hover:text-primary">{{ language.t('footer.tenantPortal') }}</a></li>
              <li><a routerLink="/login" class="transition-colors hover:text-primary">{{ language.t('footer.ownerDashboard') }}</a></li>
            </ul>
          </div>

          <div>
            <h4 class="mb-3 text-xs font-semibold uppercase tracking-wider text-ink">{{ language.t('footer.company') }}</h4>
            <ul class="space-y-2 text-xs">
              <li><a href="#" class="transition-colors hover:text-primary">{{ language.t('footer.aboutRentEasy') }}</a></li>
              <li><a href="#" class="transition-colors hover:text-primary">{{ language.t('footer.termsOfService') }}</a></li>
              <li><a href="#" class="transition-colors hover:text-primary">{{ language.t('footer.privacyPolicy') }}</a></li>
            </ul>
          </div>

          <div>
            <h4 class="mb-3 text-xs font-semibold uppercase tracking-wider text-ink">{{ language.t('footer.securityAndTrust') }}</h4>
            <p class="text-xs leading-relaxed text-ink-3">
              {{ language.t('footer.verifiedLandlordsSecurePaymentTrackingAutomated') }}
            </p>
          </div>
        </div>

        <div class="flex flex-col items-center justify-between gap-2 border-t border-hairline pt-6 text-xs text-ink-3 sm:flex-row">
          <p>&copy; 2026 RentEasy {{ language.t('footer.webPlatformAllRightsReserved') }}</p>
          <p>Powered by Django & Angular</p>
        </div>
      </div>
    </footer>
  `,
})
export class FooterComponent {
  readonly language = inject(LanguageService);
}
