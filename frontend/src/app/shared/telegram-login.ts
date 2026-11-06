import { Component, Input, OnInit, PLATFORM_ID, inject, signal } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';
import { Router } from '@angular/router';
import { AuthService } from '../services/auth.service';
import { LanguageService } from '../services/language.service';

interface TelegramLoginConfig {
  enabled: boolean;
  bot_username: string;
  bot_id: string;
  auth_url: string;
}

@Component({
  selector: 'app-telegram-login',
  template: `
    @if (enabled()) {
      <button
        type="button"
        (click)="start()"
        [disabled]="starting()"
        [attr.title]="language.t('login.telegramSignIn')"
        [attr.aria-label]="language.t('login.telegramSignIn')"
        class="grid h-11 w-11 place-items-center rounded-full bg-[#229ED9] text-white shadow-sm transition hover:brightness-110 disabled:cursor-wait disabled:opacity-70 cursor-pointer"
      >
        <svg class="h-5 w-5" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
          <path d="M9.78 18.65l.28-4.23 7.68-6.92c.34-.31-.07-.46-.52-.19L7.74 13.3 3.64 12c-.88-.25-.89-.86.2-1.3l15.97-6.16c.73-.33 1.43.18 1.15 1.3l-2.72 12.81c-.19.91-.74 1.13-1.5.71L12.6 16.3l-1.99 1.93c-.23.23-.42.42-.83.42z" />
        </svg>
      </button>
    }

    @if (dialogOpen()) {
      <div
        class="fixed inset-0 z-[100] grid place-items-center bg-black/50 p-4"
        role="presentation"
        (click)="close()"
      >
        <div
          class="app-card w-full max-w-sm p-6"
          role="dialog"
          aria-modal="true"
          [attr.aria-label]="language.t('login.telegramLoginTitle')"
          (click)="$event.stopPropagation()"
        >
          <div class="mb-4 flex items-start justify-between gap-3">
            <div class="min-w-0">
              <h2 class="text-[18px] font-extrabold tracking-tight text-ink">
                {{ language.t('login.telegramLoginTitle') }}
              </h2>
              <p class="mt-1 text-[13px] text-ink-3">
                {{ language.t('login.telegramStepOpen') }}
              </p>
            </div>
            <button
              type="button"
              (click)="close()"
              class="btn btn-ghost btn-icon shrink-0"
              [attr.aria-label]="language.t('login.telegramCancel')"
            >
              <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" d="M6 6l12 12M18 6 6 18" />
              </svg>
            </button>
          </div>

          <ol class="mb-4 space-y-2 text-[13px] text-ink-3">
            <li class="flex gap-2">
              <span class="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-primary/10 text-[11px] font-bold text-primary">1</span>
              <span>{{ language.t('login.telegramStepOpen') }}</span>
            </li>
            <li class="flex gap-2">
              <span class="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-primary/10 text-[11px] font-bold text-primary">2</span>
              <span>{{ language.t('login.telegramStepCode') }}</span>
            </li>
          </ol>

          <a
            [href]="botUrl()"
            target="_blank"
            rel="noopener"
            class="btn btn-ghost mb-4 w-full text-xs"
          >
            {{ language.t('login.telegramOpenBot') }}
          </a>

          <form (submit)="verify($event)" class="space-y-3">
            <div>
              <label class="form-label" for="telegram-login-code">
                {{ language.t('login.telegramCode') }}
              </label>
              <input
                id="telegram-login-code"
                class="form-input text-center text-2xl font-mono font-extrabold tracking-[0.4em] py-3"
                inputmode="numeric"
                maxlength="6"
                [value]="code()"
                (input)="onCodeInput($event)"
                autocomplete="one-time-code"
                autofocus
              />
            </div>

            @if (error()) {
              <div class="toast toast-error" role="alert">
                <svg class="h-4 w-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75">
                  <path d="M10.7 3.9 2.6 17.5A1.5 1.5 0 0 0 3.9 19.8h16.2a1.5 1.5 0 0 0 1.3-2.3L13.3 3.9a1.5 1.5 0 0 0-2.6 0Z" />
                  <path d="M12 9v4.2M12 16.4h.01" />
                </svg>
                <span class="flex-1">{{ error() }}</span>
              </div>
            }

            <button
              type="submit"
              [disabled]="code().length !== 6 || verifying()"
              class="btn btn-primary w-full"
            >
              {{ verifying() ? language.t('login.telegramVerifying') : language.t('login.telegramVerify') }}
            </button>
          </form>

          <p class="mt-3 text-center text-[11px] text-ink-3">
            {{ language.t('login.telegramCodeExpiry') }}
          </p>
        </div>
      </div>
    }
  `,
})
export class TelegramLoginButtonComponent implements OnInit {
  @Input() role: 'renter' | 'owner' | '' = '';

  readonly language = inject(LanguageService);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly platformId = inject(PLATFORM_ID);

  private config: TelegramLoginConfig | null = null;

  readonly enabled = signal(false);
  readonly dialogOpen = signal(false);
  readonly starting = signal(false);
  readonly verifying = signal(false);
  readonly token = signal('');
  readonly botUrl = signal('');
  readonly code = signal('');
  readonly error = signal('');

  ngOnInit(): void {
    if (!isPlatformBrowser(this.platformId)) return;

    this.auth.getTelegramLoginConfig().subscribe({
      next: (config) => {
        if (!config.enabled || !config.bot_username) return;
        this.config = config;
        this.enabled.set(true);
      },
      error: () => this.enabled.set(false),
    });
  }

  start(): void {
    if (!this.config || this.starting()) return;

    this.starting.set(true);
    this.error.set('');
    this.code.set('');

    const popup = isPlatformBrowser(this.platformId)
      ? window.open('', 'telegram_login', 'width=550,height=650')
      : null;

    this.auth.startTelegramLogin(this.role).subscribe({
      next: (res) => {
        this.starting.set(false);
        this.token.set(res.token);
        this.botUrl.set(res.url);
        this.dialogOpen.set(true);

        if (popup && !popup.closed) {
          popup.location.href = res.url;
        } else {
          window.open(res.url, '_blank', 'noopener');
        }
      },
      error: () => {
        this.starting.set(false);
        popup?.close();
        this.dialogOpen.set(true);
        this.error.set(this.language.t('login.telegramStartFailed'));
      },
    });
  }

  verify(event: Event): void {
    event.preventDefault();
    if (this.code().length !== 6 || this.verifying()) return;

    this.verifying.set(true);
    this.error.set('');

    this.auth.verifyTelegramLogin(this.token(), this.code()).subscribe({
      next: (res) => {
        this.verifying.set(false);
        this.dialogOpen.set(false);

        if (res.status === 'select_role') {
          this.router.navigateByUrl('/role-select');
        } else if (res.status === 'pending_approval') {
          this.router.navigate(['/register'], { queryParams: { pending: '1' } });
        } else {
          this.router.navigateByUrl(res.redirect || '/');
        }
      },
      error: (err) => {
        this.verifying.set(false);
        const detail = err.error?.detail || '';
        if (detail === 'invalid_code') {
          this.error.set(this.language.t('login.telegramCodeInvalid'));
        } else if (detail === 'code_expired') {
          this.error.set(this.language.t('login.telegramCodeExpired'));
        } else if (detail === 'code_not_ready') {
          this.error.set(this.language.t('login.telegramCodeNotReady'));
        } else if (detail === 'too_many_attempts') {
          this.error.set(this.language.t('login.telegramTooManyAttempts'));
        } else if (detail === 'registration_rejected') {
          this.error.set(
            this.language.t('login.yourAccountRequestWasDeclinedPleaseContactSupport')
          );
        } else if (detail === 'not_authorized') {
          this.error.set(
            this.language.t('login.thisAccountIsNotAuthorizedToSignIn')
          );
        } else {
          this.error.set(this.language.t('login.telegramLoginFailed'));
        }
      },
    });
  }

  onCodeInput(event: Event): void {
    const input = event.target as HTMLInputElement;
    const clean = input.value.replace(/\D/g, '').slice(0, 6);
    input.value = clean;
    this.code.set(clean);
  }

  close(): void {
    this.dialogOpen.set(false);
    this.token.set('');
    this.botUrl.set('');
    this.code.set('');
    this.error.set('');
  }
}
