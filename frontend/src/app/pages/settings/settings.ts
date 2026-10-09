import { Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { AuthService } from '../../services/auth.service';
import { LanguageService } from '../../services/language.service';
import { ThemeService } from '../../services/theme.service';
import { NotificationService } from '../../services/notification.service';

@Component({
  selector: 'app-settings',
  imports: [CommonModule, RouterLink],
  templateUrl: './settings.html',
})
export class SettingsComponent {
  readonly auth = inject(AuthService);
  readonly language = inject(LanguageService);
  readonly themeService = inject(ThemeService);
  readonly notifService = inject(NotificationService);

  readonly markingRead = signal(false);
  readonly markedRead = signal(false);

  setLanguage(language: 'en' | 'km'): void {
    this.language.set(language);
  }

  markAllRead(): void {
    if (this.markingRead()) return;
    this.markingRead.set(true);
    this.notifService.readAll().subscribe({
      next: () => {
        this.markingRead.set(false);
        this.markedRead.set(true);
      },
      error: () => this.markingRead.set(false),
    });
  }
}
