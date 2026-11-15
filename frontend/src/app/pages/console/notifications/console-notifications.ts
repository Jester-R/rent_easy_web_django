import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { PLATFORM_ID } from '@angular/core';
import { ConsoleService } from '../../../services/console.service';
import { LanguageService } from '../../../services/language.service';
import { ConsoleSettings } from '../../../models';

@Component({
  selector: 'app-console-notifications',
  imports: [CommonModule, FormsModule],
  templateUrl: './console-notifications.html',
})
export class ConsoleNotificationsComponent implements OnInit {
  private readonly console = inject(ConsoleService);
  private readonly platformId = inject(PLATFORM_ID);
  readonly language = inject(LanguageService);

  isLoading = signal(true);
  isSaving = signal(false);
  error = signal<string | null>(null);
  notificationMessages = signal<ConsoleSettings['notification_messages']>([]);
  broadcastTarget: 'owners' | 'renters' | 'all' = 'renters';
  broadcastTitleEn = '';
  broadcastTitleKm = '';
  broadcastBodyEn = '';
  broadcastBodyKm = '';
  broadcastSentCount = signal<number | null>(null);
  broadcastError = signal<string | null>(null);
  showBroadcastModal = signal(false);
  messagesSaved = signal(false);

  ngOnInit(): void {
    if (!isPlatformBrowser(this.platformId)) return;
    this.console.getSettings().subscribe({
      next: (res) => {
        this.notificationMessages.set(res.settings.notification_messages || []);
        this.isLoading.set(false);
      },
      error: () => {
        this.isLoading.set(false);
        this.error.set(this.language.t('consoleSettings.failedToLoadSettings'));
      },
    });
  }

  saveNotificationMessages(): void {
    this.isSaving.set(true);
    this.error.set(null);
    this.messagesSaved.set(false);
    this.console.updateSettings({ notification_messages: this.notificationMessages() }).subscribe({
      next: (res) => {
        this.notificationMessages.set(res.settings.notification_messages);
        this.isSaving.set(false);
        this.messagesSaved.set(true);
      },
      error: (err) => {
        this.isSaving.set(false);
        this.error.set(err?.error?.detail || this.language.t('consoleSettings.failedToSaveSettings'));
      },
    });
  }

  openBroadcastModal(): void {
    this.broadcastError.set(null);
    this.showBroadcastModal.set(true);
  }

  closeBroadcastModal(): void {
    if (!this.isSaving()) this.showBroadcastModal.set(false);
  }

  sendBroadcast(): void {
    const data = {
      target: this.broadcastTarget,
      title_en: this.broadcastTitleEn.trim(),
      title_km: this.broadcastTitleKm.trim(),
      body_en: this.broadcastBodyEn.trim(),
      body_km: this.broadcastBodyKm.trim(),
    };
    if (!data.title_en || !data.title_km || !data.body_en || !data.body_km) {
      this.broadcastError.set(this.language.t('consoleSettings.broadcastFieldsRequired'));
      return;
    }
    this.isSaving.set(true);
    this.broadcastError.set(null);
    this.broadcastSentCount.set(null);
    this.console.sendNotificationBroadcast(data).subscribe({
      next: (result) => {
        this.isSaving.set(false);
        this.broadcastSentCount.set(result.sent);
        this.broadcastTitleEn = '';
        this.broadcastTitleKm = '';
        this.broadcastBodyEn = '';
        this.broadcastBodyKm = '';
      },
      error: (err) => {
        this.isSaving.set(false);
        this.broadcastError.set(err?.error?.detail || this.language.t('consoleSettings.failedToSendBroadcast'));
      },
    });
  }
}
