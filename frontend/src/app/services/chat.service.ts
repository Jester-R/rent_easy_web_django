import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { HttpParams } from '@angular/common/http';
import { ChatMessage, ConversationSummary, UserBrief } from '../models';

@Injectable({
  providedIn: 'root',
})
export class ChatService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = '/api';

  getConversations(page = 1, pageSize = 20): Observable<{ conversations: ConversationSummary[]; total: number; page: number; page_size: number }> {
    return this.http.get<{ conversations: ConversationSummary[]; total: number; page: number; page_size: number }>(
      `${this.baseUrl}/conversations/`,
      { withCredentials: true, params: new HttpParams().set('page', page).set('page_size', pageSize) }
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

  getMessages(id: number, page = 1, pageSize = 50): Observable<{
    messages: ChatMessage[];
    conversation: ConversationSummary;
    other_party: UserBrief;
    total: number; page: number; page_size: number;
  }> {
    return this.http.get<{
      messages: ChatMessage[];
      conversation: ConversationSummary;
      other_party: UserBrief; total: number; page: number; page_size: number;
    }>(`${this.baseUrl}/conversations/${id}/messages/`, { withCredentials: true, params: new HttpParams().set('page', page).set('page_size', pageSize) });
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
