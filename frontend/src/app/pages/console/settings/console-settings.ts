import { Component, inject, signal, OnInit, PLATFORM_ID } from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { IconComponent } from '../../../components/icon/icon';
import { ConsoleService } from '../../../services/console.service';
import { LanguageService } from '../../../services/language.service';
import { ConsoleSettings, HomePromotion } from '../../../models';

const DEFAULT_HOME_PROMOTION: HomePromotion = {
  eyebrow_en: 'Make your next move',
  eyebrow_km: 'ចាប់ផ្តើមជំហានថ្មីរបស់អ្នក',
  title_en: 'A better way to find your next home.',
  title_km: 'ស្វែងរកផ្ទះបន្ទាប់របស់អ្នកតាមរបៀបកាន់តែងាយស្រួល។',
  body_en: 'Explore rental homes across Cambodia and connect with property owners on RentEasy.',
  body_km: 'ស្វែងរកផ្ទះជួលនៅទូទាំងប្រទេសកម្ពុជា និងភ្ជាប់ទំនាក់ទំនងជាមួយម្ចាស់អចលនទ្រព្យតាម RentEasy។',
  image_url: '',
};

function normalizeHomePromotion(value?: Partial<HomePromotion> | null): HomePromotion {
  return {
    ...DEFAULT_HOME_PROMOTION,
    ...(value || {}),
    eyebrow_en: value?.eyebrow_en ?? DEFAULT_HOME_PROMOTION.eyebrow_en,
    eyebrow_km: value?.eyebrow_km ?? DEFAULT_HOME_PROMOTION.eyebrow_km,
    title_en: value?.title_en ?? DEFAULT_HOME_PROMOTION.title_en,
    title_km: value?.title_km ?? DEFAULT_HOME_PROMOTION.title_km,
    body_en: value?.body_en ?? DEFAULT_HOME_PROMOTION.body_en,
    body_km: value?.body_km ?? DEFAULT_HOME_PROMOTION.body_km,
    image_url: value?.image_url ?? '',
  };
}

@Component({
  selector: 'app-console-settings',
  imports: [CommonModule, FormsModule, IconComponent],
  templateUrl: './console-settings.html',
})
export class ConsoleSettingsComponent implements OnInit {
  private readonly console = inject(ConsoleService);
  private readonly platformId = inject(PLATFORM_ID);
  readonly language = inject(LanguageService);

  isLoading = signal(true);
  isSaving = signal(false);
  error = signal<string | null>(null);
  promotionSaved = signal(false);
  autoApproveOwners = signal(false);
  homePromotion = signal<ConsoleSettings['home_promotion']>(DEFAULT_HOME_PROMOTION);

  ngOnInit(): void {
    // The SSR renderer has no browser session cookie, so this request fails
    // during a direct page load. Load settings after hydration in the browser.
    if (!isPlatformBrowser(this.platformId)) return;

    this.console.getSettings().subscribe({
      next: (res) => {
        this.autoApproveOwners.set(res.settings.auto_approve_owners);
        this.homePromotion.set(normalizeHomePromotion(res.settings.home_promotion));
        this.isLoading.set(false);
      },
      error: () => {
        this.isLoading.set(false);
        this.error.set(this.language.t('consoleSettings.failedToLoadSettings'));
      },
    });
  }

  toggleAutoApprove(): void {
    const next = !this.autoApproveOwners();
    this.autoApproveOwners.set(next);
    this.isSaving.set(true);
    this.error.set(null);
    this.console.updateSettings({ auto_approve_owners: next }).subscribe({
      next: (res) => {
        this.autoApproveOwners.set(res.settings.auto_approve_owners);
        this.isSaving.set(false);
      },
      error: () => {
        this.autoApproveOwners.set(!next);
        this.isSaving.set(false);
        this.error.set(this.language.t('consoleSettings.failedToSaveSettings'));
      },
    });
  }

  saveHomePromotion(): void {
    const submitted = normalizeHomePromotion(this.homePromotion());
    this.isSaving.set(true);
    this.error.set(null);
    this.console.updateSettings({ home_promotion: submitted }).subscribe({
      next: (res) => {
        this.isSaving.set(false);
        const savedPromotion = normalizeHomePromotion(res.settings.home_promotion);
        if (JSON.stringify(savedPromotion) !== JSON.stringify(submitted)) {
          this.promotionSaved.set(false);
          this.error.set('The server did not retain the promotion. Restart the backend, then save again.');
          return;
        }
        this.homePromotion.set(savedPromotion);
        this.promotionSaved.set(true);
      },
      error: (err) => {
        this.isSaving.set(false);
        this.error.set(err?.error?.detail || this.language.t('consoleSettings.failedToSaveSettings'));
      },
    });
  }

  updateHomePromotion(field: keyof ConsoleSettings['home_promotion'], value: string): void {
    this.homePromotion.update((promotion) => ({ ...normalizeHomePromotion(promotion), [field]: value }));
    this.promotionSaved.set(false);
  }

  onPromotionImageSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    if (!['image/jpeg', 'image/png', 'image/webp', 'image/gif'].includes(file.type)) {
      this.error.set('Choose a JPG, PNG, WebP, or GIF image.');
      input.value = '';
      return;
    }
    if (file.size > 2 * 1024 * 1024) {
      this.error.set('Choose an image smaller than 2 MB.');
      input.value = '';
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === 'string') {
        this.updateHomePromotion('image_url', reader.result);
        this.error.set(null);
      }
    };
    reader.onerror = () => this.error.set('Could not read this image. Try another file.');
    reader.readAsDataURL(file);
  }
}
