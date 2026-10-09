import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { ChatMessage, ConversationSummary, UserBrief } from '../models';

@Injectable({
  providedIn: 'root',
})
export class ChatService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = '/api';

  getConversations(): Observable<{ conversations: ConversationSummary[] }> {
    return this.http.get<{ conversations: ConversationSummary[] }>(
      `${this.baseUrl}/conversations/`,
      { withCredentials: true }
    );
  }

  startConversation(
    propertyId: number,
    message?: string
  ): Observable<{ conversation: ConversationSummary }> {
    return this.http.post<{ conversation: ConversationSummary }>(
      `${this.baseUrl}/conversations/`,
      { property_id: propertyId, message: message || '' },
      { withCredentials: true }
    );
  }

  getMessages(id: number): Observable<{
    messages: ChatMessage[];
    conversation: ConversationSummary;
    other_party: UserBrief;
  }> {
    return this.http.get<{
      messages: ChatMessage[];
      conversation: ConversationSummary;
      other_party: UserBrief;
    }>(`${this.baseUrl}/conversations/${id}/messages/`, { withCredentials: true });
  }

  sendMessage(id: number, body: string): Observable<{ message: ChatMessage }> {
    return this.http.post<{ message: ChatMessage }>(
      `${this.baseUrl}/conversations/${id}/messages/`,
      { body },
      { withCredentials: true }
    );
  }

  markRead(id: number): Observable<{ ok: boolean; unread: number }> {
    return this.http.post<{ ok: boolean; unread: number }>(
      `${this.baseUrl}/conversations/${id}/read/`,
      {},
      { withCredentials: true }
    );
  }
}
