import {
  Component,
  ElementRef,
  OnDestroy,
  OnInit,
  PLATFORM_ID,
  inject,
  input,
  signal,
  viewChild,
} from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { ChatService } from '../../services/chat.service';
import { AuthService } from '../../services/auth.service';
import { LanguageService } from '../../services/language.service';
import { ChatMessage, ConversationSummary, UserBrief } from '../../models';
import { prettyDate } from '../../shared/ui';
import { DataPaginationComponent } from '../../components/data-pagination/data-pagination';

@Component({
  selector: 'app-chat-thread',
  imports: [CommonModule, FormsModule, RouterLink, DataPaginationComponent],
  templateUrl: './thread.html',
})
export class ChatThreadComponent implements OnInit, OnDestroy {
  readonly id = input.required<string>();
  readonly language = inject(LanguageService);
  readonly auth = inject(AuthService);
  readonly prettyDate = prettyDate;

  private readonly chat = inject(ChatService);
  private readonly platformId = inject(PLATFORM_ID);
  private readonly scroller = viewChild<ElementRef<HTMLDivElement>>('scroller');

  messages = signal<ChatMessage[]>([]);
  conversation = signal<ConversationSummary | null>(null);
  otherParty = signal<UserBrief | null>(null);
  isLoading = signal(true);
  isSending = signal(false);
  sendError = signal(false);
  page = signal(1);
  total = signal(0);
  readonly pageSize = 50;
  draft = '';

  private timer: ReturnType<typeof setInterval> | null = null;

  ngOnInit(): void {
    if (isPlatformBrowser(this.platformId)) {
      this.load();
      this.timer = setInterval(() => this.refresh(), 8000);
    }
  }

  ngOnDestroy(): void {
    if (this.timer) clearInterval(this.timer);
  }

  private get conversationId(): number {
    return Number(this.id());
  }

  load(): void {
    this.chat.getMessages(this.conversationId, this.page(), this.pageSize).subscribe({
      next: (res) => {
        this.messages.set(res.messages);
        this.conversation.set(res.conversation);
        this.otherParty.set(res.other_party);
        this.total.set(res.total);
        this.isLoading.set(false);
        this.scrollToBottom();
      },
      error: () => this.isLoading.set(false),
    });
  }

  refresh(): void {
    if (this.isSending()) return;
    this.chat.getMessages(this.conversationId, this.page(), this.pageSize).subscribe({
      next: (res) => {
        this.messages.set(res.messages);
        this.otherParty.set(res.other_party);
        this.total.set(res.total);
        this.scrollToBottom();
      },
    });
  }

  changePage(page: number): void { this.page.set(page); this.load(); }

  isMine(message: ChatMessage): boolean {
    return message.sender_id === this.auth.currentUser()?.id;
  }

  send(): void {
    const body = this.draft.trim();
    if (!body || this.isSending()) return;
    this.isSending.set(true);
    this.sendError.set(false);
    this.chat.sendMessage(this.conversationId, body).subscribe({
      next: (res) => {
        this.draft = '';
        this.isSending.set(false);
        this.page.set(1);
        this.load();
      },
      error: () => {
        this.isSending.set(false);
        this.sendError.set(true);
      },
    });
  }

  private scrollToBottom(): void {
    setTimeout(() => {
      const el = this.scroller()?.nativeElement;
      if (el) el.scrollTop = el.scrollHeight;
    }, 0);
  }
}
