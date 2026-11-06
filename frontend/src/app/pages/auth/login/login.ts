import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { AuthService } from '../../../services/auth.service';
import { LanguageService } from '../../../services/language.service';
import { TelegramLoginButtonComponent } from '../../../shared/telegram-login';

@Component({
  selector: 'app-login',
  imports: [CommonModule, ReactiveFormsModule, RouterLink, TelegramLoginButtonComponent],
  templateUrl: './login.html',
})
export class LoginComponent implements OnInit {
  readonly language = inject(LanguageService);
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  errorMessage = signal<string | null>(null);
  isLoading = signal(false);

  form = this.fb.group({
    identifier: ['', [Validators.required]],
    password: ['', [Validators.required]],
  });

  ngOnInit(): void {
    const error = this.route.snapshot.queryParamMap.get('error');
    if (error) {
      if (error === 'oauth_cancelled') {
        this.errorMessage.set(this.language.t('login.oauthCancelled'));
      } else if (error === 'oauth_not_configured') {
        this.errorMessage.set(this.language.t('login.oauthNotConfigured'));
      } else if (error === 'oauth_missing_parameters') {
        this.errorMessage.set(this.language.t('login.oauthMissingParameters'));
      } else if (error === 'oauth_invalid_state') {
        this.errorMessage.set(this.language.t('login.oauthInvalidState'));
      } else if (error === 'approval_pending') {
        this.errorMessage.set(
          this.language.t('login.yourAccountIsAwaitingApprovalByASystem')
        );
      } else if (error === 'registration_rejected') {
        this.errorMessage.set(
          this.language.t('login.yourAccountRequestWasDeclinedPleaseContactSupport')
        );
      } else if (error === 'not_authorized') {
        this.errorMessage.set(
          this.language.t('login.thisAccountIsNotAuthorizedToSignIn')
        );
      } else if (error === 'telegram_not_configured') {
        this.errorMessage.set(this.language.t('login.telegramNotConfigured'));
      } else if (
        error === 'telegram_invalid' ||
        error === 'telegram_account_failed'
      ) {
        this.errorMessage.set(this.language.t('login.telegramLoginFailed'));
      } else {
        this.errorMessage.set(this.language.t('login.oauthFailed'));
      }
    }
  }

  loginWithGoogle(): void {
    this.auth.loginWithGoogle();
  }

  onSubmit(): void {
    if (this.form.invalid) return;

    this.isLoading.set(true);
    this.errorMessage.set(null);

    const val = this.form.value;
    this.auth
      .login({
        identifier: val.identifier || '',
        password: val.password || '',
      })
      .subscribe({
        next: (res) => {
          this.isLoading.set(false);
          if (res.user.role === 'owner') {
            this.router.navigate(['/owner']);
          } else if (res.user.role === 'renter') {
            this.router.navigate(['/rent']);
          } else if (res.user.is_superadmin_role) {
            this.router.navigate(['/console']);
          } else {
            this.router.navigate(['/']);
          }
        },
        error: (err) => {
          this.isLoading.set(false);
          const detail = err.error?.detail || '';
          if (detail === 'approval_pending') {
            this.errorMessage.set(
              this.language.t('login.yourAccountIsAwaitingApprovalByASystem')
            );
          } else if (detail === 'registration_rejected') {
            this.errorMessage.set(
              this.language.t('login.yourAccountRequestWasDeclinedPleaseContactSupport')
            );
          } else if (detail === 'not_authorized') {
            this.errorMessage.set(
              this.language.t('login.thisAccountIsNotAuthorizedToSignIn')
            );
          } else if (detail.startsWith('registration_unverified:')) {
            const email = detail.slice('registration_unverified:'.length);
            this.errorMessage.set(this.language.t('login.emailNotVerified'));
            this.router.navigate(['/register'], {
              queryParams: { email, verify: '1' },
            });
          } else if (detail === 'email_not_verified') {
            this.errorMessage.set(this.language.t('login.emailNotVerified'));
            this.router.navigate(['/register'], {
              queryParams: { verify: '1' },
            });
          } else if (detail === 'invalid_credentials') {
            this.errorMessage.set(this.language.t('login.invalidUsernameEmailOrPassword'));
          } else if (detail === 'credentials_required') {
            this.errorMessage.set(this.language.t('login.pleaseProvideBothIdentifierAndPassword'));
          } else {
            this.errorMessage.set(this.language.t('login.anErrorOccurredDuringLoginPleaseTryAgain'));
          }
        },
      });
  }

  fillDemo(role: 'renter' | 'owner' | 'admin'): void {
    if (role === 'renter') {
      this.form.patchValue({ identifier: 'renter', password: 'renter' });
    } else if (role === 'owner') {
      this.form.patchValue({ identifier: 'owner', password: 'owner' });
    } else {
      this.form.patchValue({ identifier: 'admin', password: 'admin' });
    }
  }
}
