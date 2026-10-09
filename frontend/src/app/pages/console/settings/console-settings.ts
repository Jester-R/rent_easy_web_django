import { Component, inject, signal, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { IconComponent } from '../../../components/icon/icon';
import { ConsoleService } from '../../../services/console.service';
import { LanguageService } from '../../../services/language.service';

@Component({
  selector: 'app-console-settings',
  imports: [CommonModule, IconComponent],
  templateUrl: './console-settings.html',
})
export class ConsoleSettingsComponent implements OnInit {
  private readonly console = inject(ConsoleService);
  readonly language = inject(LanguageService);

  isLoading = signal(true);
  isSaving = signal(false);
  error = signal<string | null>(null);
  saved = signal(false);
  autoApproveOwners = signal(false);

  ngOnInit(): void {
    this.console.getSettings().subscribe({
      next: (res) => {
        this.autoApproveOwners.set(res.settings.auto_approve_owners);
        this.isLoading.set(false);
      },
      error: () => {
        this.isLoading.set(false);
        this.error.set(this.language.t('Failed to load settings.', 'មិនអាចផ្ទុកការកំណត់បានទេ។'));
      },
    });
  }

  toggleAutoApprove(): void {
    const next = !this.autoApproveOwners();
    this.autoApproveOwners.set(next);
    this.isSaving.set(true);
    this.error.set(null);
    this.console.updateSettings({ auto_approve_owners: next }).subscribe({
      next: (res) => {
        this.autoApproveOwners.set(res.settings.auto_approve_owners);
        this.isSaving.set(false);
      },
      error: () => {
        this.autoApproveOwners.set(!next);
        this.isSaving.set(false);
        this.error.set(this.language.t('Failed to save settings.', 'មិនអាចរក្សាទុកការកំណត់បានទេ។'));
      },
    });
  }
}