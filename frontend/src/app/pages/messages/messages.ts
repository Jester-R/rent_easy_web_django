import { Component, inject, PLATFORM_ID, signal } from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { RouterLink } from '@angular/router';
import { ChatService, ConversationFilters } from '../../services/chat.service';
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
  chatType = signal<'all' | 'general' | 'refund'>('all');
  participant = signal<'all' | 'renter' | 'owner' | 'admin'>('all');
  propertyQuery = signal('');
  dateFrom = signal('');
  dateTo = signal('');
  search = signal('');
  page = signal(1);
  readonly pageSize = 20;
  total = signal(0);

  constructor() {
    if (isPlatformBrowser(this.platformId)) this.load();
  }

  load(): void {
    this.isLoading.set(true);
    this.loadError.set(false);
    const filters: ConversationFilters = {
      chatType: this.chatType(),
      participant: this.participant(),
      property: this.propertyQuery(),
      dateFrom: this.dateFrom(),
      dateTo: this.dateTo(),
      search: this.search(),
    };
    this.chat.getConversations(this.page(), this.pageSize, filters).subscribe({
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

  conversationTitle(conversation: ConversationSummary): string {
    if (!conversation.is_refund_support) {
      return conversation.other_party?.display_name || 'User';
    }
    return conversation.refund_label || [conversation.renter?.display_name, conversation.owner?.display_name]
      .filter(Boolean)
      .join(' · ') || 'Refund support';
  }

  changePage(page: number): void { this.page.set(page); this.load(); }

  changeChatType(type: 'all' | 'general' | 'refund'): void {
    if (this.chatType() === type) return;
    this.chatType.set(type);
    this.page.set(1);
    this.load();
  }

  changeParticipant(participant: 'all' | 'renter' | 'owner' | 'admin'): void {
    this.participant.set(participant);
    this.page.set(1);
    this.load();
  }

  applyFilters(): void {
    this.page.set(1);
    this.load();
  }

  resetFilters(): void {
    this.chatType.set('all');
    this.participant.set('all');
    this.propertyQuery.set('');
    this.dateFrom.set('');
    this.dateTo.set('');
    this.search.set('');
    this.page.set(1);
    this.load();
  }
}
