import { Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../../../services/auth.service';
import { LanguageService } from '../../../services/language.service';

@Component({
  selector: 'app-register',
  imports: [CommonModule, ReactiveFormsModule, RouterLink],
  templateUrl: './register.html',
})
export class RegisterComponent {
  readonly language = inject(LanguageService);
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  errorMessage = signal<string | null>(null);
  isLoading = signal(false);
  role = signal<'renter' | 'owner'>('renter');
  pendingApproval = signal(false);

  form = this.fb.group({
    full_name: [''],
    username: ['', [Validators.required, Validators.minLength(3)]],
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required, Validators.minLength(6)]],
    password_confirm: ['', [Validators.required]],
  });

  selectRole(role: 'renter' | 'owner'): void {
    this.role.set(role);
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
          if (res.status === 'pending_approval') {
            this.pendingApproval.set(true);
            return;
          }
          this.router.navigateByUrl(res.redirect || '/');
        },
        error: (err) => {
          this.isLoading.set(false);
          const detail = err.error?.detail || '';
          if (detail === 'email_taken') {
            this.errorMessage.set(this.language.t('register.thisEmailAddressIsAlreadyRegistered'));
          } else if (detail === 'username_taken') {
            this.errorMessage.set(this.language.t('register.thisUsernameIsAlreadyTaken'));
          } else if (detail === 'username_invalid') {
            this.errorMessage.set(this.language.t('register.usernameMustBeAlphanumeric'));
          } else {
            this.errorMessage.set(this.language.t('register.registrationFailedPleaseCheckYourDetails'));
          }
        },
      });
  }
}
