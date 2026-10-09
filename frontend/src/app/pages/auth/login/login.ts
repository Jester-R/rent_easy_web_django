import { Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../../../services/auth.service';
import { LanguageService } from '../../../services/language.service';

@Component({
  selector: 'app-login',
  imports: [CommonModule, ReactiveFormsModule, RouterLink],
  templateUrl: './login.html',
})
export class LoginComponent {
  readonly language = inject(LanguageService);
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  errorMessage = signal<string | null>(null);
  isLoading = signal(false);

  form = this.fb.group({
    identifier: ['', [Validators.required]],
    password: ['', [Validators.required]],
  });

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
              this.language.t(
                'Your account is awaiting approval by a system administrator.',
                'គណនីរបស់អ្នកកំពុងរង់ចាំការអនុម័តពីអ្នកគ្រប់គ្រងប្រព័ន្ធ។'
              )
            );
          } else if (detail === 'registration_rejected') {
            this.errorMessage.set(
              this.language.t(
                'Your account request was declined. Please contact support.',
                'សំណើគណនីរបស់អ្នកត្រូវបានបដិសេធ។ សូមទាក់ទងផ្នែកជំនួយ។'
              )
            );
          } else if (detail === 'not_authorized') {
            this.errorMessage.set(
              this.language.t(
                'This account is not authorized to sign in.',
                'គណនីនេះមិនត្រូវបានអនុញ្ញាតឱ្យចូលប្រើប្រាស់ទេ។'
              )
            );
          } else if (detail === 'invalid_credentials') {
            this.errorMessage.set(this.language.t('Invalid username/email or password.', 'ឈ្មោះអ្នកប្រើ/អ៊ីមែល ឬពាក្យសម្ងាត់មិនត្រឹមត្រូវទេ។'));
          } else if (detail === 'credentials_required') {
            this.errorMessage.set(this.language.t('Please provide both identifier and password.', 'សូមបញ្ចូលឈ្មោះអ្នកប្រើ ឬអ៊ីមែល និងពាក្យសម្ងាត់។'));
          } else {
            this.errorMessage.set(this.language.t('An error occurred during login. Please try again.', 'មានបញ្ហាក្នុងពេលចូលគណនី។ សូមព្យាយាមម្ដងទៀត។'));
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
