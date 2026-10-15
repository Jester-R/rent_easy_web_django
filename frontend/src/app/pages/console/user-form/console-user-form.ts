import { Component, inject, input, OnInit, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { IconComponent } from '../../../components/icon/icon';
import {
  SearchableSelectComponent,
  SelectOption,
} from '../../../components/searchable-select/searchable-select';
import { ConsoleService } from '../../../services/console.service';
import { LanguageService } from '../../../services/language.service';
import { User } from '../../../models';
import { prettyDate, roleLabel } from '../../../shared/ui';

@Component({
  selector: 'app-console-user-form',
  imports: [ReactiveFormsModule, RouterLink, IconComponent, SearchableSelectComponent],
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
    return this.language.valueLabel(roleLabel(role));
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

  readonly roleSelectOptions: SelectOption[] = this.roleOptions.map((role) => ({
    value: role,
    label: this.roleLabelTranslated(role),
  }));

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
        this.errorMessage.set(this.friendlyError(err, 'consoleUserForm.failedToLoadUser'));
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
        this.errorMessage.set(this.friendlyError(err, 'consoleUserForm.failedToSaveUser'));
      },
    });
  }

  private friendlyError(err: unknown, fallbackKey: string): string {
    const detail = (err as { error?: { detail?: string } }).error?.detail;
    if (!detail) return this.language.t(fallbackKey);
    const detailKeys: Record<string, string> = {
      email_taken: 'consoleUserForm.emailTaken',
      password_too_short: 'consoleUserForm.passwordMustBeAtLeast6Characters',
      username_invalid: 'consoleUserForm.usernameInvalid',
      title_required: 'consoleUserForm.titleRequired',
      location_required: 'consoleUserForm.locationRequired',
      price_required: 'consoleUserForm.priceRequired',
      owner_required: 'consoleUserForm.ownerRequired',
      'Email or username already in use': 'consoleUserForm.emailTaken',
      'Password must be at least 6 characters.': 'consoleUserForm.passwordMustBeAtLeast6Characters',
      'Username must be 3-30 characters using letters, numbers, ., _ or -':
        'consoleUserForm.usernameInvalid',
      'Title is required': 'consoleUserForm.titleRequired',
      'Location is required': 'consoleUserForm.locationRequired',
      'Enter a valid price': 'consoleUserForm.priceRequired',
      'Select an owner with the Property Owner role.': 'consoleUserForm.ownerRequired',
    };
    const key = detailKeys[detail];
    if (key) return this.language.t(key);
    return detail;
  }
}
