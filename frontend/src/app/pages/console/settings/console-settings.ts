import { Component, inject, signal, OnInit, PLATFORM_ID } from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { IconComponent } from '../../../components/icon/icon';
import { ConsoleService } from '../../../services/console.service';
import { LanguageService } from '../../../services/language.service';
import { ConsoleSettings, HomePromotion } from '../../../models';
import { PropertyCategoryService } from '../../../services/property-category.service';

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
  private readonly propertyCategoryService = inject(PropertyCategoryService);
  private readonly platformId = inject(PLATFORM_ID);
  readonly language = inject(LanguageService);

  isLoading = signal(true);
  isSaving = signal(false);
  error = signal<string | null>(null);
  saved = signal(false);
  promotionSaved = signal(false);
  categoriesSaved = signal(false);
  autoApproveOwners = signal(false);
  categories = signal<ConsoleSettings['property_categories']>([]);
  editingCategoryIndexes = signal<number[]>([]);
  notificationMessages = signal<ConsoleSettings['notification_messages']>([]);
  homePromotion = signal<ConsoleSettings['home_promotion']>(DEFAULT_HOME_PROMOTION);
  broadcastTarget: 'owners' | 'renters' | 'all' = 'renters';
  broadcastTitleEn = '';
  broadcastTitleKm = '';
  broadcastBodyEn = '';
  broadcastBodyKm = '';
  broadcastSentCount = signal<number | null>(null);

  ngOnInit(): void {
    // The SSR renderer has no browser session cookie, so this request fails
    // during a direct page load. Load settings after hydration in the browser.
    if (!isPlatformBrowser(this.platformId)) return;

    this.console.getSettings().subscribe({
      next: (res) => {
        this.autoApproveOwners.set(res.settings.auto_approve_owners);
        this.categories.set(res.settings.property_categories || []);
        this.notificationMessages.set(res.settings.notification_messages || []);
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

  addCategory(): void {
    const existing = new Set(this.categories().map((item) => item.value.trim().toLowerCase()));
    const base = `new_category_${Date.now().toString(36)}`;
    let value = base.slice(0, 24);
    let suffix = 1;
    while (existing.has(value)) {
      const tail = `_${suffix++}`;
      value = `${base.slice(0, 24 - tail.length)}${tail}`;
    }
    this.categories.update((items) => {
      const next = [...items, {
        value,
        label_en: 'New category',
        label_km: 'ប្រភេទថ្មី',
      }];
      this.editingCategoryIndexes.set([next.length - 1]);
      return next;
    });
    this.categoriesSaved.set(false);
  }

  isCategoryEditing(index: number): boolean {
    return this.editingCategoryIndexes().includes(index);
  }

  updateCategory(index: number, field: 'value' | 'label_en' | 'label_km', value: string): void {
    this.categories.update((items) => items.map((item, itemIndex) =>
      itemIndex === index ? { ...item, [field]: value } : item
    ));
    this.categoriesSaved.set(false);
  }

  toggleCategoryEditing(index: number): void {
    this.editingCategoryIndexes.update((indexes) =>
      indexes.includes(index) ? indexes.filter((item) => item !== index) : [...indexes, index]
    );
  }

  removeCategory(value: string): void {
    this.categories.update((items) => items.filter((item) => item.value !== value));
    this.editingCategoryIndexes.set([]);
    this.categoriesSaved.set(false);
  }

  saveCategories(): void {
    const categories = this.categories().map((item) => ({
      ...item,
      value: item.value.trim().toLowerCase().replace(/[^a-z0-9_-]+/g, '_').slice(0, 24),
      label_en: item.label_en.trim(),
      label_km: item.label_km.trim(),
    }));
    const keys = categories.map((item) => item.value);
    if (categories.some((item) => !item.value || !item.label_en || !item.label_km)) {
      this.error.set(this.language.t('consoleSettings.categoryFieldsRequired'));
      return;
    }
    if (new Set(keys).size !== keys.length) {
      this.error.set(this.language.t('consoleSettings.categoryKeysMustBeUnique'));
      return;
    }
    this.categories.set(categories);
    this.isSaving.set(true);
    this.error.set(null);
    this.console.updateSettings({ property_categories: categories }).subscribe({
      next: (res) => {
        this.categories.set(res.settings.property_categories);
        this.propertyCategoryService.setCategories(res.settings.property_categories);
        this.editingCategoryIndexes.set([]);
        this.categoriesSaved.set(true);
        this.isSaving.set(false);
        this.saved.set(true);
      },
      error: (err) => {
        this.isSaving.set(false);
        this.error.set(err?.error?.detail || this.language.t('consoleSettings.failedToSaveSettings'));
      },
    });
  }

  saveNotificationMessages(): void {
    this.isSaving.set(true);
    this.error.set(null);
    this.console.updateSettings({ notification_messages: this.notificationMessages() }).subscribe({
      next: (res) => {
        this.notificationMessages.set(res.settings.notification_messages);
        this.isSaving.set(false);
        this.saved.set(true);
      },
      error: (err) => {
        this.isSaving.set(false);
        this.error.set(err?.error?.detail || this.language.t('consoleSettings.failedToSaveSettings'));
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

  sendBroadcast(): void {
    const data = {
      target: this.broadcastTarget,
      title_en: this.broadcastTitleEn.trim(),
      title_km: this.broadcastTitleKm.trim(),
      body_en: this.broadcastBodyEn.trim(),
      body_km: this.broadcastBodyKm.trim(),
    };
    if (!data.title_en || !data.title_km || !data.body_en || !data.body_km) {
      this.error.set(this.language.t('consoleSettings.broadcastFieldsRequired'));
      return;
    }
    this.isSaving.set(true);
    this.error.set(null);
    this.broadcastSentCount.set(null);
    this.console.sendNotificationBroadcast(data).subscribe({
      next: (result) => {
        this.isSaving.set(false);
        this.broadcastSentCount.set(result.sent);
        this.broadcastTitleEn = '';
        this.broadcastTitleKm = '';
        this.broadcastBodyEn = '';
        this.broadcastBodyKm = '';
      },
      error: (err) => {
        this.isSaving.set(false);
        this.error.set(err?.error?.detail || this.language.t('consoleSettings.failedToSendBroadcast'));
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
