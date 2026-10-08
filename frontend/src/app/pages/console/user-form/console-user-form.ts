import { Component, inject, input, OnInit, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { IconComponent } from '../../../components/icon/icon';
import { ConsoleService } from '../../../services/console.service';
import { LanguageService } from '../../../services/language.service';
import { User } from '../../../models';
import { prettyDate, roleLabel } from '../../../shared/ui';

@Component({
  selector: 'app-console-user-form',
  imports: [ReactiveFormsModule, RouterLink, IconComponent],
  templateUrl: './console-user-form.html',
})
export class ConsoleUserFormComponent implements OnInit {
  readonly id = input<string>();
  readonly language = inject(LanguageService);

  private readonly fb = inject(FormBuilder);
  private readonly console = inject(ConsoleService);
  private readonly router = inject(Router);

  readonly prettyDate = prettyDate;
  readonly roleLabel = roleLabel;

  roleLabelTranslated(role: string): string {
    const label = roleLabel(role);
    const khmer: Record<string, string> = {
      'Super Admin': 'អ្នកគ្រប់គ្រងកំពូល',
      'Property Owner': 'ម្ចាស់អចលនទ្រព្យ',
      Renter: 'អ្នកជួល',
    };
    return this.language.current() === 'km' ? (khmer[label] ?? label) : label;
  }

  isEdit = signal(false);
  isLoading = signal(true);
  isSaving = signal(false);
  submitted = signal(false);
  errorMessage = signal<string | null>(null);
  user = signal<User | null>(null);

  form = this.fb.group({
    full_name: ['', [Validators.maxLength(120)]],
    username: ['', [Validators.required, Validators.maxLength(30)]],
    email: ['', [Validators.required, Validators.email]],
    role: ['renter', [Validators.required]],
    password: [''],
    is_active: [true],
  });

  roleOptions = ['renter', 'owner', 'superadmin'];

  ngOnInit(): void {
    const editId = this.id();
    if (editId) {
      this.isEdit.set(true);
      this.loadUser(Number(editId));
    } else {
      this.form.get('password')?.setValidators([Validators.required]);
      this.form.get('password')?.updateValueAndValidity();
      this.isLoading.set(false);
    }
  }

  loadUser(id: number): void {
    this.isLoading.set(true);
    this.console.getUser(id).subscribe({
      next: (res) => {
        this.isLoading.set(false);
        this.user.set(res.user);
        this.form.patchValue({
          full_name: res.user.full_name,
          username: res.user.username,
          email: res.user.email,
          role: res.user.role,
          is_active: res.user.is_active,
        });
      },
      error: (err) => {
        this.isLoading.set(false);
        this.errorMessage.set(this.friendlyError(err, 'Failed to load user.'));
      },
    });
  }

  showError(name: string): boolean {
    const control = this.form.get(name);
    return !!control && control.invalid && (control.touched || control.dirty || this.submitted());
  }

  onSubmit(): void {
    this.submitted.set(true);
    this.errorMessage.set(null);
    if (this.form.invalid) return;

    this.isSaving.set(true);
    const value = this.form.value;
    const payload: Record<string, unknown> = {
      full_name: value.full_name || '',
      username: value.username || '',
      email: value.email || '',
      role: value.role || 'renter',
      is_active: !!value.is_active,
    };
    const password = value.password || '';
    if (password) payload['password'] = password;

    const editId = this.id();
    const request = editId
      ? this.console.updateUser(Number(editId), payload)
      : this.console.createUser(payload);

    request.subscribe({
      next: () => {
        this.isSaving.set(false);
        this.router.navigate(['/console/users']);
      },
      error: (err) => {
        this.isSaving.set(false);
        this.errorMessage.set(this.friendlyError(err, 'Failed to save user.'));
      },
    });
  }

  private friendlyError(err: unknown, fallback: string): string {
    const detail = (err as { error?: { detail?: string } }).error?.detail;
    if (!detail) {
      return this.language.t(fallback, fallback === 'Failed to load user.' ? 'មិនអាចផ្ទុកព័ត៌មានអ្នកប្រើប្រាស់បានទេ។' : 'មិនអាចរក្សាទុកអ្នកប្រើប្រាស់បានទេ។');
    }
    const messages: Record<string, string> = {
      email_taken: 'Email or username already in use',
      password_too_short: 'Password must be at least 6 characters.',
      username_invalid: 'Username must be 3-30 characters using letters, numbers, ., _ or -',
      title_required: 'Title is required',
      location_required: 'Location is required',
      price_required: 'Enter a valid price',
      owner_required: 'Select an owner with the Property Owner role.',
    };
    const message = messages[detail] || detail;
    const khmer: Record<string, string> = {
      'Email or username already in use': 'អ៊ីមែល ឬឈ្មោះអ្នកប្រើនេះត្រូវបានប្រើរួចហើយ។',
      'Password must be at least 6 characters.': 'ពាក្យសម្ងាត់ត្រូវមានយ៉ាងតិច ៦ តួអក្សរ។',
      'Username must be 3-30 characters using letters, numbers, ., _ or -': 'ឈ្មោះអ្នកប្រើត្រូវមាន ៣–៣០ តួអក្សរ ដោយប្រើអក្សរ លេខ . _ ឬ -។',
      'Title is required': 'ត្រូវបញ្ចូលចំណងជើង។',
      'Location is required': 'ត្រូវបញ្ចូលទីតាំង។',
      'Enter a valid price': 'សូមបញ្ចូលតម្លៃត្រឹមត្រូវ។',
    };
    return this.language.current() === 'km' ? (khmer[message] ?? message) : message;
  }
}
