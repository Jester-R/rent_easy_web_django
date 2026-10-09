import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { AuthService } from '../../services/auth.service';
import { LanguageService } from '../../services/language.service';

@Component({
  selector: 'app-profile',
  imports: [CommonModule, ReactiveFormsModule],
  templateUrl: './profile.html',
})
export class ProfileComponent implements OnInit {
  readonly language = inject(LanguageService);
  private readonly fb = inject(FormBuilder);
  readonly auth = inject(AuthService);

  successMessage = signal<string | null>(null);
  errorMessage = signal<string | null>(null);
  isLoading = signal(false);

  form = this.fb.group({
    full_name: [''],
    username: ['', [Validators.required]],
    email: ['', [Validators.required, Validators.email]],
    avatar_url: [''],
  });

  ngOnInit(): void {
    const user = this.auth.currentUser();
    if (user) {
      this.form.patchValue({
        full_name: user.full_name,
        username: user.username,
        email: user.email,
        avatar_url: user.avatar_url || '',
      });
    }
  }

  onSubmit(): void {
    if (this.form.invalid) return;

    this.isLoading.set(true);
    this.successMessage.set(null);
    this.errorMessage.set(null);

    const val = this.form.value;
    this.auth
        .updatePreferences({
          full_name: val.full_name || '',
          username: val.username || '',
          email: val.email || '',
          avatar_url: val.avatar_url || '',
        })
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
          } else {
            this.errorMessage.set('Failed to update profile.');
          }
        },
      });
  }
}
