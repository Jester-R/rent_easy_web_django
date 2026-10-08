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
              {{ language.t('Modern property rental ecosystem connecting verified owners with quality tenants across Cambodia and beyond.', 'ប្រព័ន្ធជួលអចលនទ្រព្យទំនើប ភ្ជាប់ម្ចាស់ផ្ទះដែលបានផ្ទៀងផ្ទាត់ជាមួយអ្នកជួលដែលមានគុណភាពនៅកម្ពុជា និងតំបន់ផ្សេងៗ។') }}
            </p>
          </div>

          <div>
            <h4 class="mb-3 text-xs font-semibold uppercase tracking-wider text-ink">{{ language.t('Explore', 'ស្វែងរក') }}</h4>
            <ul class="space-y-2 text-xs">
              <li><a routerLink="/browse" class="transition-colors hover:text-primary">{{ language.t('Browse Listings', 'មើលអចលនទ្រព្យ') }}</a></li>
              <li><a routerLink="/login" class="transition-colors hover:text-primary">{{ language.t('Tenant Portal', 'ផ្ទាំងអ្នកជួល') }}</a></li>
              <li><a routerLink="/login" class="transition-colors hover:text-primary">{{ language.t('Owner Dashboard', 'ផ្ទាំងម្ចាស់ផ្ទះ') }}</a></li>
            </ul>
          </div>

          <div>
            <h4 class="mb-3 text-xs font-semibold uppercase tracking-wider text-ink">{{ language.t('Company', 'ក្រុមហ៊ុន') }}</h4>
            <ul class="space-y-2 text-xs">
              <li><a href="#" class="transition-colors hover:text-primary">{{ language.t('About RentEasy', 'អំពី RentEasy') }}</a></li>
              <li><a href="#" class="transition-colors hover:text-primary">{{ language.t('Terms of Service', 'លក្ខខណ្ឌសេវាកម្ម') }}</a></li>
              <li><a href="#" class="transition-colors hover:text-primary">{{ language.t('Privacy Policy', 'គោលការណ៍ឯកជនភាព') }}</a></li>
            </ul>
          </div>

          <div>
            <h4 class="mb-3 text-xs font-semibold uppercase tracking-wider text-ink">{{ language.t('Security & Trust', 'សុវត្ថិភាព និងទំនុកចិត្ត') }}</h4>
            <p class="text-xs leading-relaxed text-ink-3">
              {{ language.t('Verified landlords, secure payment tracking, automated lease agreements, and transparent booking fees.', 'ម្ចាស់ផ្ទះដែលបានផ្ទៀងផ្ទាត់ ការតាមដានការទូទាត់ប្រកបដោយសុវត្ថិភាព កិច្ចសន្យាជួលស្វ័យប្រវត្តិ និងតម្លៃកក់ប្រកបដោយតម្លាភាព។') }}
            </p>
          </div>
        </div>

        <div class="flex flex-col items-center justify-between gap-2 border-t border-hairline pt-6 text-xs text-ink-3 sm:flex-row">
          <p>&copy; 2026 RentEasy {{ language.t('Web Platform. All rights reserved.', 'វេទិកាអនឡាញ។ រក្សាសិទ្ធិគ្រប់យ៉ាង។') }}</p>
          <p>Powered by Django & Angular</p>
        </div>
      </div>
    </footer>
  `,
})
export class FooterComponent {
  readonly language = inject(LanguageService);
}
