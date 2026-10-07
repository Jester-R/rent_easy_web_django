import { Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../../../services/auth.service';

@Component({
  selector: 'app-login',
  imports: [CommonModule, ReactiveFormsModule, RouterLink],
  templateUrl: './login.html',
})
export class LoginComponent {
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
          if (detail === 'invalid_credentials') {
            this.errorMessage.set('Invalid username/email or password.');
          } else if (detail === 'credentials_required') {
            this.errorMessage.set('Please provide both identifier and password.');
          } else {
            this.errorMessage.set('An error occurred during login. Please try again.');
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
