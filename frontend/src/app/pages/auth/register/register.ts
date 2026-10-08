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

  form = this.fb.group({
    full_name: [''],
    username: ['', [Validators.required, Validators.minLength(3)]],
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required, Validators.minLength(6)]],
    password_confirm: ['', [Validators.required]],
  });

  onSubmit(): void {
    if (this.form.invalid) return;

    const val = this.form.value;
    if (val.password !== val.password_confirm) {
      this.errorMessage.set(this.language.t('Passwords do not match.', 'ពាក្យសម្ងាត់មិនត្រូវគ្នាទេ។'));
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
      })
      .subscribe({
        next: () => {
          this.isLoading.set(false);
          this.router.navigate(['/role-select']);
        },
        error: (err) => {
          this.isLoading.set(false);
          const detail = err.error?.detail || '';
          if (detail === 'email_taken') {
            this.errorMessage.set(this.language.t('This email address is already registered.', 'អាសយដ្ឋានអ៊ីមែលនេះបានចុះឈ្មោះរួចហើយ។'));
          } else if (detail === 'username_taken') {
            this.errorMessage.set(this.language.t('This username is already taken.', 'ឈ្មោះអ្នកប្រើនេះត្រូវបានប្រើរួចហើយ។'));
          } else if (detail === 'username_invalid') {
            this.errorMessage.set(this.language.t('Username must be alphanumeric.', 'ឈ្មោះអ្នកប្រើត្រូវមានតែអក្សរ និងលេខ។'));
          } else {
            this.errorMessage.set(this.language.t('Registration failed. Please check your details.', 'ការចុះឈ្មោះបរាជ័យ។ សូមពិនិត្យព័ត៌មានរបស់អ្នក។'));
          }
        },
      });
  }
}
