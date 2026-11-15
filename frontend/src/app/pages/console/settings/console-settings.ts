import { Component, inject, signal, OnInit, PLATFORM_ID } from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { IconComponent } from '../../../components/icon/icon';
import { ConsoleService } from '../../../services/console.service';
import { LanguageService } from '../../../services/language.service';
import {
  ConsoleSettings,
  HomePromotion,
  PaymentMethodDetail,
} from '../../../models';

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

  paymentMethodDetails = signal<Record<string, PaymentMethodDetail>>({});
  abaPaywayMerchantId = signal('');
  abaPaywayApiKey = signal('');
  abaPaywayApiKeyConfigured = signal(false);
  abaPaywayApiKeyFromEnv = signal(false);
  clearAbaPaywayApiKey = signal(false);
  isPaymentMethodSaving = signal(false);
  paymentMethodError = signal<string | null>(null);

  stripePublishableKey = signal('');
  stripeSecretKey = signal('');
  stripeWebhookSecret = signal('');
  stripeSecretConfigured = signal(false);
  stripeWebhookConfigured = signal(false);
  stripeSecretFromEnv = signal(false);
  stripeWebhookFromEnv = signal(false);
  clearStripeSecret = signal(false);
  clearStripeWebhookSecret = signal(false);
  isStripeSaving = signal(false);
  stripeError = signal<string | null>(null);

  googleClientId = signal('');
  googleClientSecret = signal('');
  googleRedirectUri = signal('');
  googleClientSecretConfigured = signal(false);
  googleClientSecretFromEnv = signal(false);
  clearGoogleClientSecret = signal(false);
  isGoogleSaving = signal(false);
  googleError = signal<string | null>(null);

  telegramBotToken = signal('');
  telegramBotUsername = signal('');
  telegramWebhookSecret = signal('');
  telegramWebhookUrl = signal('');
  telegramChatId = signal('');
  telegramLoginAuthUrl = signal('');
  telegramBotTokenConfigured = signal(false);
  telegramBotTokenFromEnv = signal(false);
  telegramWebhookSecretConfigured = signal(false);
  telegramWebhookSecretFromEnv = signal(false);
  clearTelegramBotToken = signal(false);
  clearTelegramWebhookSecret = signal(false);
  isTelegramSaving = signal(false);
  telegramError = signal<string | null>(null);
  isTelegramWebhookSaving = signal(false);
  telegramWebhookStatus = signal<string | null>(null);
  telegramWebhookError = signal<string | null>(null);

  ngOnInit(): void {
    // The SSR renderer has no browser session cookie, so this request fails
    // during a direct page load. Load settings after hydration in the browser.
    if (!isPlatformBrowser(this.platformId)) return;

    this.console.getSettings().subscribe({
      next: (res) => {
        this.autoApproveOwners.set(res.settings.auto_approve_owners);
        this.homePromotion.set(normalizeHomePromotion(res.settings.home_promotion));
        this.paymentMethodDetails.set(res.settings.payment_method_details || {});
        this.setIntegrationSettings(res.settings);
        this.setStripeSettings(res.settings);
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

  private setIntegrationSettings(settings: ConsoleSettings): void {
    this.abaPaywayMerchantId.set(settings.aba_payway_merchant_id || '');
    this.abaPaywayApiKeyConfigured.set(!!settings.aba_payway_api_key_configured);
    this.abaPaywayApiKeyFromEnv.set(!!settings.aba_payway_api_key_from_env);
    this.clearAbaPaywayApiKey.set(false);

    this.googleClientId.set(settings.google_oauth_client_id || '');
    this.googleRedirectUri.set(settings.google_oauth_redirect_uri || '');
    this.googleClientSecretConfigured.set(
      !!settings.google_oauth_client_secret_configured
    );
    this.googleClientSecretFromEnv.set(
      !!settings.google_oauth_client_secret_from_env
    );
    this.clearGoogleClientSecret.set(false);

    this.telegramBotUsername.set(settings.telegram_bot_username || '');
    this.telegramWebhookUrl.set(settings.telegram_webhook_url || '');
    this.telegramChatId.set(settings.telegram_chat_id || '');
    this.telegramLoginAuthUrl.set(settings.telegram_login_auth_url || '');
    this.telegramBotTokenConfigured.set(
      !!settings.telegram_bot_token_configured
    );
    this.telegramBotTokenFromEnv.set(!!settings.telegram_bot_token_from_env);
    this.telegramWebhookSecretConfigured.set(
      !!settings.telegram_webhook_secret_configured
    );
    this.telegramWebhookSecretFromEnv.set(
      !!settings.telegram_webhook_secret_from_env
    );
    this.clearTelegramBotToken.set(false);
    this.clearTelegramWebhookSecret.set(false);
  }

  private setStripeSettings(settings: ConsoleSettings): void {
    this.stripePublishableKey.set(settings.stripe_publishable_key || '');
    this.stripeSecretConfigured.set(!!settings.stripe_secret_key_configured);
    this.stripeWebhookConfigured.set(!!settings.stripe_webhook_secret_configured);
    this.stripeSecretFromEnv.set(!!settings.stripe_secret_key_from_env);
    this.stripeWebhookFromEnv.set(!!settings.stripe_webhook_secret_from_env);
    this.clearStripeSecret.set(false);
    this.clearStripeWebhookSecret.set(false);
  }

  updatePaymentMethodDetail(field: keyof PaymentMethodDetail, value: string): void {
    this.paymentMethodDetails.update((details) => ({
      ...details,
      'ABA Pay': {
        ...(details['ABA Pay'] || {
          account_name: '',
          account_number: '',
          instructions_en: '',
          instructions_km: '',
        }),
        [field]: value,
      },
    }));
  }

  savePaymentMethodDetails(): void {
    this.isPaymentMethodSaving.set(true);
    this.paymentMethodError.set(null);
    const payload: {
      payment_method_details: Record<string, PaymentMethodDetail>;
      aba_payway_merchant_id: string;
      aba_payway_api_key?: string;
      clear_aba_payway_api_key?: boolean;
    } = {
      payment_method_details: this.paymentMethodDetails(),
      aba_payway_merchant_id: this.abaPaywayMerchantId().trim(),
    };
    const apiKey = this.abaPaywayApiKey().trim();
    if (apiKey) payload.aba_payway_api_key = apiKey;
    if (this.clearAbaPaywayApiKey()) payload.clear_aba_payway_api_key = true;
    this.console.updateSettings(payload).subscribe({
      next: (res) => {
        this.paymentMethodDetails.set(res.settings.payment_method_details);
        this.abaPaywayMerchantId.set(res.settings.aba_payway_merchant_id || '');
        this.abaPaywayApiKeyConfigured.set(
          !!res.settings.aba_payway_api_key_configured
        );
        this.abaPaywayApiKeyFromEnv.set(
          !!res.settings.aba_payway_api_key_from_env
        );
        this.abaPaywayApiKey.set('');
        this.clearAbaPaywayApiKey.set(false);
        this.isPaymentMethodSaving.set(false);
      },
      error: (err) => {
        this.isPaymentMethodSaving.set(false);
        this.paymentMethodError.set(
          err?.error?.detail || this.language.t('consoleSettings.failedToSaveSettings')
        );
      },
    });
  }

  saveStripeSettings(): void {
    this.isStripeSaving.set(true);
    this.stripeError.set(null);
    const payload: {
      stripe_publishable_key: string;
      stripe_secret_key?: string;
      stripe_webhook_secret?: string;
      clear_stripe_secret_key?: boolean;
      clear_stripe_webhook_secret?: boolean;
    } = {
      stripe_publishable_key: this.stripePublishableKey().trim(),
    };
    const secretKey = this.stripeSecretKey().trim();
    const webhookSecret = this.stripeWebhookSecret().trim();
    if (secretKey) payload.stripe_secret_key = secretKey;
    if (webhookSecret) payload.stripe_webhook_secret = webhookSecret;
    if (this.clearStripeSecret()) payload.clear_stripe_secret_key = true;
    if (this.clearStripeWebhookSecret()) {
      payload.clear_stripe_webhook_secret = true;
    }
    this.console.updateSettings(payload).subscribe({
      next: (res) => {
        this.setStripeSettings(res.settings);
        this.stripeSecretKey.set('');
        this.stripeWebhookSecret.set('');
        this.isStripeSaving.set(false);
      },
      error: (err) => {
        this.isStripeSaving.set(false);
        this.stripeError.set(
          err?.error?.detail || this.language.t('consoleSettings.failedToSaveSettings')
        );
      },
    });
  }

  saveGoogleSettings(): void {
    this.isGoogleSaving.set(true);
    this.googleError.set(null);
    const payload: {
      google_oauth_client_id: string;
      google_oauth_redirect_uri: string;
      google_oauth_client_secret?: string;
      clear_google_oauth_client_secret?: boolean;
    } = {
      google_oauth_client_id: this.googleClientId().trim(),
      google_oauth_redirect_uri: this.googleRedirectUri().trim(),
    };
    const clientSecret = this.googleClientSecret().trim();
    if (clientSecret) payload.google_oauth_client_secret = clientSecret;
    if (this.clearGoogleClientSecret()) {
      payload.clear_google_oauth_client_secret = true;
    }
    this.console.updateSettings(payload).subscribe({
      next: (res) => {
        this.setIntegrationSettings(res.settings);
        this.googleClientSecret.set('');
        this.isGoogleSaving.set(false);
      },
      error: (err) => {
        this.isGoogleSaving.set(false);
        this.googleError.set(
          err?.error?.detail || this.language.t('consoleSettings.failedToSaveSettings')
        );
      },
    });
  }

  registerTelegramWebhook(): void {
    this.isTelegramWebhookSaving.set(true);
    this.telegramWebhookStatus.set(null);
    this.telegramWebhookError.set(null);
    this.console.registerTelegramWebhook().subscribe({
      next: (res) => {
        this.isTelegramWebhookSaving.set(false);
        this.telegramWebhookStatus.set(
          res.description ||
            this.language.t('profile.telegramWebhookRegistered')
        );
      },
      error: (err) => {
        this.isTelegramWebhookSaving.set(false);
        this.telegramWebhookError.set(
          err?.error?.detail ||
            this.language.t('profile.telegramWebhookRegisterFailed')
        );
      },
    });
  }

  saveTelegramSettings(): void {
    this.isTelegramSaving.set(true);
    this.telegramError.set(null);
    const payload: {
      telegram_bot_username: string;
      telegram_webhook_url: string;
      telegram_chat_id: string;
      telegram_login_auth_url: string;
      telegram_bot_token?: string;
      telegram_webhook_secret?: string;
      clear_telegram_bot_token?: boolean;
      clear_telegram_webhook_secret?: boolean;
    } = {
      telegram_bot_username: this.telegramBotUsername().trim(),
      telegram_webhook_url: this.telegramWebhookUrl().trim(),
      telegram_chat_id: this.telegramChatId().trim(),
      telegram_login_auth_url: this.telegramLoginAuthUrl().trim(),
    };
    const token = this.telegramBotToken().trim();
    const webhookSecret = this.telegramWebhookSecret().trim();
    if (token) payload.telegram_bot_token = token;
    if (webhookSecret) payload.telegram_webhook_secret = webhookSecret;
    if (this.clearTelegramBotToken()) payload.clear_telegram_bot_token = true;
    if (this.clearTelegramWebhookSecret()) {
      payload.clear_telegram_webhook_secret = true;
    }
    this.console.updateSettings(payload).subscribe({
      next: (res) => {
        this.setIntegrationSettings(res.settings);
        this.telegramBotToken.set('');
        this.telegramWebhookSecret.set('');
        this.isTelegramSaving.set(false);
      },
      error: (err) => {
        this.isTelegramSaving.set(false);
        this.telegramError.set(
          err?.error?.detail || this.language.t('consoleSettings.failedToSaveSettings')
        );
      },
    });
  }
}
