import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { firstValueFrom } from 'rxjs';
import { AuthService } from '../../services/auth.service';
import { LanguageService } from '../../services/language.service';
import { ConsoleService } from '../../services/console.service';
import { compressImageToFile } from '../../shared/image';
import type { PaymentMethodDetail, PayoutAccountDetails } from '../../models';

@Component({
  selector: 'app-profile',
  imports: [CommonModule, ReactiveFormsModule],
  templateUrl: './profile.html',
})
export class ProfileComponent implements OnInit {
  readonly language = inject(LanguageService);
  private readonly fb = inject(FormBuilder);
  readonly auth = inject(AuthService);
  private readonly console = inject(ConsoleService);
  payoutAccounts = signal<Record<string, PayoutAccountDetails>>({});
  paymentMethodDetails = signal<Record<string, PaymentMethodDetail>>({});
  abaPaywayMerchantId = signal('');
  isPaymentMethodSaving = signal(false);
  paymentMethodError = signal<string | null>(null);

  successMessage = signal<string | null>(null);
  errorMessage = signal<string | null>(null);
  isLoading = signal(false);
  photoError = signal<string | null>(null);
  isPhotoReading = signal(false);
  telegramLink = signal<string | null>(null);
  isTelegramLoading = signal(false);

  form = this.fb.group({
    full_name: [''],
    username: ['', [Validators.required]],
    email: ['', [Validators.required, Validators.email]],
    avatar_url: [''],
    payment_account_name: [''],
    payment_account_number: [''],
    payment_phone: [''],
  });

  ngOnInit(): void {
    const user = this.auth.currentUser();
    if (user) {
      const payoutAccounts: Record<string, PayoutAccountDetails> = {};
      const abaAccount = user.payout_accounts?.['aba'];
      if (abaAccount) {
        payoutAccounts['aba'] = { ...abaAccount };
      }
      if (user.payout_method === 'aba' && !payoutAccounts['aba']) {
        payoutAccounts[user.payout_method] = {
          account_name: user.payout_account_name || '',
          account_number: user.payout_account_number || '',
          bank_name: user.payout_bank_name || '',
          phone: user.payout_phone || '',
          note: user.payout_note || '',
        };
      }
      this.payoutAccounts.set(payoutAccounts);
      this.form.patchValue({
        full_name: user.full_name,
        username: user.username,
        email: user.email,
        avatar_url: user.avatar_url || '',
        payment_account_name: user.payment_account_name || '',
        payment_account_number: user.payment_account_number || '',
        payment_phone: user.payment_phone || '',
      });
      if (this.auth.isAdmin()) {
        this.console.getSettings().subscribe({
          next: (res) => {
            this.paymentMethodDetails.set(res.settings.payment_method_details || {});
            this.abaPaywayMerchantId.set(res.settings.aba_payway_merchant_id || '');
          },
          error: () => this.paymentMethodError.set(this.language.t('consoleSettings.failedToLoadSettings')),
        });
      }
    }
  }

  updatePaymentMethodDetail(field: keyof PaymentMethodDetail, value: string): void {
    this.paymentMethodDetails.update((details) => ({
      ...details,
      'ABA Pay': {
        ...(details['ABA Pay'] || { account_name: '', account_number: '', instructions_en: '', instructions_km: '' }),
        [field]: value,
      },
    }));
  }

  savePaymentMethodDetails(): void {
    this.isPaymentMethodSaving.set(true);
    this.paymentMethodError.set(null);
    this.console.updateSettings({
      payment_method_details: this.paymentMethodDetails(),
      aba_payway_merchant_id: this.abaPaywayMerchantId().trim(),
    }).subscribe({
      next: (res) => {
        this.paymentMethodDetails.set(res.settings.payment_method_details);
        this.abaPaywayMerchantId.set(res.settings.aba_payway_merchant_id || '');
        this.isPaymentMethodSaving.set(false);
      },
      error: (err) => {
        this.isPaymentMethodSaving.set(false);
        this.paymentMethodError.set(err?.error?.detail || this.language.t('consoleSettings.failedToSaveSettings'));
      },
    });
  }

  async onPhotoSelected(event: Event): Promise<void> {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    this.photoError.set(null);
    if (!file) return;
    if (!['image/jpeg', 'image/png', 'image/webp', 'image/gif'].includes(file.type)) {
      this.photoError.set('Choose a JPG, PNG, WebP, or GIF image.');
      input.value = '';
      return;
    }
    if (file.size > 12 * 1024 * 1024) {
      this.photoError.set('Choose an image smaller than 12 MB.');
      input.value = '';
      return;
    }

    this.isPhotoReading.set(true);
    this.photoError.set(null);
    try {
      // Shrink camera photos before uploading; mobile images are often
      // several megabytes even when the selected file looks small.
      const compressed = await compressImageToFile(file, 512, 0.82);
      const res = await firstValueFrom(this.auth.uploadAvatar(compressed));
      this.form.controls.avatar_url.setValue(res.url);
    } catch (error) {
      const detail = (error as { error?: { detail?: string } })?.error?.detail;
      if (detail === 'image_too_large') {
        this.photoError.set('Choose an image smaller than 12 MB.');
      } else if (detail === 'invalid_image_file') {
        this.photoError.set('Choose a valid JPG, PNG, WebP, or GIF image.');
      } else {
        this.photoError.set('Could not upload this image. Try another file.');
      }
    } finally {
      this.isPhotoReading.set(false);
      input.value = '';
    }
  }

  onSubmit(): void {
    if (this.form.invalid) return;

    this.isLoading.set(true);
    this.successMessage.set(null);
    this.errorMessage.set(null);

    const val = this.form.value;
    const payload: {
      full_name: string;
      username: string;
      email: string;
      avatar_url: string;
      payment_account_name?: string;
      payment_account_number?: string;
      payment_phone?: string;
      payout_method?: string;
      payout_accounts?: Record<string, PayoutAccountDetails>;
    } = {
      full_name: val.full_name || '',
      username: val.username || '',
      email: val.email || '',
      avatar_url: val.avatar_url || '',
    };
    if (this.auth.isRenter()) {
      payload.payment_account_name = val.payment_account_name || '';
      payload.payment_account_number = val.payment_account_number || '';
      payload.payment_phone = val.payment_phone || '';
    }
    if (this.auth.isOwner()) {
      payload['payout_method'] = 'aba';
      payload['payout_accounts'] = this.payoutAccounts();
    }
    this.auth
        .updatePreferences(payload)
      .subscribe({
        next: () => {
          this.isLoading.set(false);
          this.successMessage.set('Profile successfully updated.');
        },
        error: (err) => {
          this.isLoading.set(false);
          const detail = err.error?.detail || '';
          if (detail === 'email_taken') {
            this.errorMessage.set('This email is already used by another account.');
          } else if (detail === 'username_taken') {
            this.errorMessage.set('This username is already taken.');
          } else if (detail === 'payout_method_invalid') {
            this.errorMessage.set('Choose a valid payout method.');
          } else {
            this.errorMessage.set('Failed to update profile.');
          }
        },
      });
  }

  updatePayoutAccount(method: string, field: keyof PayoutAccountDetails, value: string): void {
    const empty: PayoutAccountDetails = { account_name: '', account_number: '', bank_name: '', phone: '', note: '' };
    this.payoutAccounts.update((accounts) => ({
      ...accounts,
      [method]: { ...(accounts[method] || empty), [field]: value },
    }));
  }

  connectTelegram(): void {
    this.isTelegramLoading.set(true);
    this.errorMessage.set(null);
    this.auth.createTelegramLink().subscribe({
      next: (res) => { this.telegramLink.set(res.url); this.isTelegramLoading.set(false); },
      error: (err) => {
        this.isTelegramLoading.set(false);
        this.errorMessage.set(err.error?.detail === 'telegram_bot_not_configured' ? 'Telegram bot is not configured yet.' : 'Could not create the Telegram connection link.');
      },
    });
  }

  refreshTelegramStatus(): void {
    this.isTelegramLoading.set(true);
    this.auth.getPreferences().subscribe({
      next: (res) => { this.auth.currentUser.set(res.user); this.isTelegramLoading.set(false); this.telegramLink.set(null); },
      error: () => { this.isTelegramLoading.set(false); this.errorMessage.set('Could not refresh Telegram connection status.'); },
    });
  }

  disconnectTelegram(): void {
    this.isTelegramLoading.set(true);
    this.auth.unlinkTelegram().subscribe({
      next: () => { this.isTelegramLoading.set(false); this.telegramLink.set(null); },
      error: () => { this.isTelegramLoading.set(false); this.errorMessage.set('Could not disconnect Telegram.'); },
    });
  }
}
