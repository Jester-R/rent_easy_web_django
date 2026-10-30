import { Component, inject, OnInit, PLATFORM_ID, signal } from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { RouterLink } from '@angular/router';
import { ChatService } from '../../services/chat.service';
import { LanguageService } from '../../services/language.service';
import { ConversationSummary } from '../../models';
import { prettyDate } from '../../shared/ui';
import { DataPaginationComponent } from '../../components/data-pagination/data-pagination';

@Component({
  selector: 'app-messages',
  imports: [CommonModule, RouterLink, DataPaginationComponent],
  templateUrl: './messages.html',
})
export class MessagesComponent {
  readonly language = inject(LanguageService);
  readonly prettyDate = prettyDate;

  private readonly chat = inject(ChatService);
  private readonly platformId = inject(PLATFORM_ID);

  conversations = signal<ConversationSummary[]>([]);
  isLoading = signal(true);
  loadError = signal(false);
  page = signal(1);
  readonly pageSize = 20;
  total = signal(0);

  constructor() {
    if (isPlatformBrowser(this.platformId)) this.load();
  }

  load(): void {
    this.isLoading.set(true);
    this.loadError.set(false);
    this.chat.getConversations(this.page(), this.pageSize).subscribe({
      next: (res) => {
        this.conversations.set(res.conversations);
        this.total.set(res.total);
        this.isLoading.set(false);
      },
      error: () => {
        this.loadError.set(true);
        this.isLoading.set(false);
      },
    });
  }

  changePage(page: number): void { this.page.set(page); this.load(); }
}
