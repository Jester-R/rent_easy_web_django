import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormsModule, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { AuthService } from '../../../services/auth.service';
import { LanguageService } from '../../../services/language.service';
import { TelegramLoginButtonComponent } from '../../../shared/telegram-login';

@Component({
  selector: 'app-register',
  imports: [CommonModule, FormsModule, ReactiveFormsModule, RouterLink, TelegramLoginButtonComponent],
  templateUrl: './register.html',
})
export class RegisterComponent implements OnInit {
  readonly language = inject(LanguageService);
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  errorMessage = signal<string | null>(null);
  otpSuccessMessage = signal<string | null>(null);
  isLoading = signal(false);
  isVerifyingOtp = signal(false);
  isResendingOtp = signal(false);
  role = signal<'renter' | 'owner'>('renter');
  step = signal<'form' | 'otp' | 'pending' | 'success'>('form');
  registeredHomeUrl = signal<string>('/rent');
  otpEmail = signal<string>('');
  otpCode = signal<string>('');

  form = this.fb.group({
    full_name: [''],
    username: ['', [Validators.required, Validators.minLength(3)]],
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required, Validators.minLength(6)]],
    password_confirm: ['', [Validators.required]],
  });

  ngOnInit(): void {
    const pending = this.route.snapshot.queryParamMap.get('pending');
    if (pending === '1') {
      this.step.set('pending');
    }
    const pendingEmail = this.route.snapshot.queryParamMap.get('email');
    if (pendingEmail) {
      this.form.patchValue({ email: pendingEmail });
      this.otpEmail.set(pendingEmail);
      if (this.route.snapshot.queryParamMap.get('verify') === '1') {
        this.step.set('otp');
        this.otpSuccessMessage.set(this.language.t('register.verifyPendingEmail'));
      }
    }
    const error = this.route.snapshot.queryParamMap.get('error');
    if (error) {
      if (error === 'oauth_cancelled') {
        this.errorMessage.set(this.language.t('login.oauthCancelled'));
      } else if (error === 'oauth_not_configured') {
        this.errorMessage.set(this.language.t('login.oauthNotConfigured'));
      } else if (error === 'email_taken') {
        this.errorMessage.set(
          this.language.t('register.thisEmailAddressIsAlreadyRegistered')
        );
      } else {
        this.errorMessage.set(this.language.t('login.oauthFailed'));
      }
    }
  }

  selectRole(role: 'renter' | 'owner'): void {
    this.role.set(role);
  }

  signUpWithGoogle(): void {
    this.auth.loginWithGoogle(this.role());
  }

  onSubmit(): void {
    if (this.form.invalid) return;

    const val = this.form.value;
    if (val.password !== val.password_confirm) {
      this.errorMessage.set(this.language.t('register.passwordsDoNotMatch'));
      return;
    }

    this.isLoading.set(true);
    this.errorMessage.set(null);
    this.otpSuccessMessage.set(null);

    this.auth
      .register({
        full_name: val.full_name || '',
        username: val.username || '',
        email: val.email || '',
        password: val.password || '',
        password_confirm: val.password_confirm || '',
        role: this.role(),
      })
      .subscribe({
        next: (res) => {
          this.isLoading.set(false);
          if (res.status === 'otp_required') {
            this.otpEmail.set(res.email || val.email || '');
            this.otpCode.set('');
            this.step.set('otp');
            return;
          }
          if (res.status === 'pending_approval') {
            this.step.set('pending');
            return;
          }
          this.router.navigateByUrl(res.redirect || '/');
        },
        error: (err) => {
          this.isLoading.set(false);
          const detail = err.error?.detail || '';
          if (detail === 'disposable_email_not_allowed') {
            this.errorMessage.set(
              this.language.t('register.disposableEmailNotAllowed')
            );
          } else if (detail === 'email_domain_invalid') {
            this.errorMessage.set(
              this.language.t('register.emailDomainInvalid')
            );
          } else if (detail === 'invalid_email_format') {
            this.errorMessage.set(
              this.language.t('register.invalidEmailFormat')
            );
          } else if (detail === 'email_taken') {
            this.errorMessage.set(
              this.language.t('register.thisEmailAddressIsAlreadyRegistered')
            );
          } else if (detail === 'username_taken') {
            this.errorMessage.set(
              this.language.t('register.thisUsernameIsAlreadyTaken')
            );
          } else if (detail === 'username_invalid') {
            this.errorMessage.set(
              this.language.t('register.usernameMustBeAlphanumeric')
            );
          } else {
            this.errorMessage.set(
              this.language.t('register.registrationFailedPleaseCheckYourDetails')
            );
          }
        },
      });
  }

  onOtpInput(event: Event): void {
    const input = event.target as HTMLInputElement;
    const clean = input.value.replace(/\D/g, '').slice(0, 6);
    input.value = clean;
    this.otpCode.set(clean);
  }

  onVerifyOtp(): void {
    const code = this.otpCode().trim();
    if (code.length !== 6) return;

    this.isVerifyingOtp.set(true);
    this.errorMessage.set(null);
    this.otpSuccessMessage.set(null);

    this.auth.verifyRegisterOtp(this.otpEmail(), code).subscribe({
      next: (res) => {
        this.isVerifyingOtp.set(false);
        if (res.status === 'pending_approval') {
          this.step.set('pending');
          return;
        }
        this.registeredHomeUrl.set((res.redirect || res.home_url || '/rent').replace(/\/+$/, ''));
        this.step.set('success');
      },
      error: (err) => {
        this.isVerifyingOtp.set(false);
        const detail = err.error?.detail || '';
        if (detail.startsWith('invalid_otp_code')) {
          this.errorMessage.set(this.language.t('register.invalidOtpCode'));
        } else if (detail === 'otp_expired_or_invalid') {
          this.errorMessage.set(this.language.t('register.otpExpired'));
        } else if (detail === 'too_many_attempts') {
          this.errorMessage.set(this.language.t('register.tooManyAttempts'));
        } else if (detail === 'email_taken') {
          this.errorMessage.set(
            this.language.t('register.thisEmailAddressIsAlreadyRegistered')
          );
        } else {
          this.errorMessage.set(
            this.language.t('register.registrationFailedPleaseCheckYourDetails')
          );
        }
      },
    });
  }

  onResendOtp(): void {
    this.isResendingOtp.set(true);
    this.errorMessage.set(null);
    this.otpSuccessMessage.set(null);

    this.auth.resendRegisterOtp(this.otpEmail()).subscribe({
      next: () => {
        this.isResendingOtp.set(false);
        this.otpSuccessMessage.set(this.language.t('register.codeResent'));
      },
      error: (err) => {
        this.isResendingOtp.set(false);
        const detail = err.error?.detail || '';
        if (detail.startsWith('resend_cooldown')) {
          this.errorMessage.set('Please wait a moment before requesting another code.');
        } else {
          this.errorMessage.set('Failed to resend code. Please try again.');
        }
      },
    });
  }

  backToForm(): void {
    this.step.set('form');
    this.errorMessage.set(null);
    this.otpSuccessMessage.set(null);
  }

  goToDashboard(): void {
    const dest = this.registeredHomeUrl() || '/rent';
    this.router.navigateByUrl(dest);
  }
}

