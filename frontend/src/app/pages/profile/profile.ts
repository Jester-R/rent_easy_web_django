import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { AuthService } from '../../services/auth.service';
import { LanguageService } from '../../services/language.service';
import { PAYOUT_METHODS } from '../../shared/ui';

@Component({
  selector: 'app-profile',
  imports: [CommonModule, ReactiveFormsModule],
  templateUrl: './profile.html',
})
export class ProfileComponent implements OnInit {
  readonly language = inject(LanguageService);
  private readonly fb = inject(FormBuilder);
  readonly auth = inject(AuthService);
  readonly payoutMethods = PAYOUT_METHODS;

  successMessage = signal<string | null>(null);
  errorMessage = signal<string | null>(null);
  isLoading = signal(false);
  photoError = signal<string | null>(null);
  isPhotoReading = signal(false);

  form = this.fb.group({
    full_name: [''],
    username: ['', [Validators.required]],
    email: ['', [Validators.required, Validators.email]],
    avatar_url: [''],
    payout_method: [''],
    payout_account_name: [''],
    payout_account_number: [''],
    payout_bank_name: [''],
    payout_phone: [''],
    payout_note: [''],
  });

  ngOnInit(): void {
    const user = this.auth.currentUser();
    if (user) {
      this.form.patchValue({
        full_name: user.full_name,
        username: user.username,
        email: user.email,
        avatar_url: user.avatar_url || '',
        payout_method: user.payout_method || '',
        payout_account_name: user.payout_account_name || '',
        payout_account_number: user.payout_account_number || '',
        payout_bank_name: user.payout_bank_name || '',
        payout_phone: user.payout_phone || '',
        payout_note: user.payout_note || '',
      });
    }
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
    if (file.size > 2 * 1024 * 1024) {
      this.photoError.set('Choose an image smaller than 2 MB.');
      input.value = '';
      return;
    }

    const reader = new FileReader();
    this.isPhotoReading.set(true);
    reader.onload = () => {
      if (typeof reader.result === 'string') {
        this.form.controls.avatar_url.setValue(reader.result);
      }
      this.isPhotoReading.set(false);
    };
    reader.onerror = () => {
      this.isPhotoReading.set(false);
      this.photoError.set('Could not read this image. Try another file.');
    };
    reader.readAsDataURL(file);
  }

  onSubmit(): void {
    if (this.form.invalid) return;

    this.isLoading.set(true);
    this.successMessage.set(null);
    this.errorMessage.set(null);

    const val = this.form.value;
    const payload: Record<string, string> = {
      full_name: val.full_name || '',
      username: val.username || '',
      email: val.email || '',
      avatar_url: val.avatar_url || '',
    };
    if (this.auth.isOwner()) {
      payload['payout_method'] = val.payout_method || '';
      payload['payout_account_name'] = val.payout_account_name || '';
      payload['payout_account_number'] = val.payout_account_number || '';
      payload['payout_bank_name'] = val.payout_bank_name || '';
      payload['payout_phone'] = val.payout_phone || '';
      payload['payout_note'] = val.payout_note || '';
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
}
