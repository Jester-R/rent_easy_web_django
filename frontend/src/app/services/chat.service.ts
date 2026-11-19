import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { HttpParams } from '@angular/common/http';
import { ChatMessage, ConversationSummary, UserBrief } from '../models';

export interface ConversationFilters {
  chatType?: 'all' | 'general' | 'refund';
  participant?: 'all' | 'renter' | 'owner' | 'admin';
  property?: string;
  dateFrom?: string;
  dateTo?: string;
  search?: string;
}

@Injectable({
  providedIn: 'root',
})
export class ChatService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = '/api';

  getConversations(page = 1, pageSize = 20, filters: ConversationFilters = {}): Observable<{ conversations: ConversationSummary[]; total: number; page: number; page_size: number }> {
    let params = new HttpParams()
      .set('page', page)
      .set('page_size', pageSize)
      .set('chat_type', filters.chatType || 'all')
      .set('participant', filters.participant || 'all');
    if (filters.property) params = params.set('property', filters.property);
    if (filters.dateFrom) params = params.set('date_from', filters.dateFrom);
    if (filters.dateTo) params = params.set('date_to', filters.dateTo);
    if (filters.search) params = params.set('search', filters.search);
    return this.http.get<{ conversations: ConversationSummary[]; total: number; page: number; page_size: number }>(
      `${this.baseUrl}/conversations/`,
      { withCredentials: true, params }
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

  openBookingChat(
    bookingId: number
  ): Observable<{ conversation: ConversationSummary }> {
    return this.http.post<{ conversation: ConversationSummary }>(
      `${this.baseUrl}/bookings/${bookingId}/chat/`,
      {},
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

  openRefundChat(
    refundId: number,
    party?: 'renter' | 'owner'
  ): Observable<{ ok: boolean; conversation_id: number; url: string }> {
    return this.http.post<{ ok: boolean; conversation_id: number; url: string }>(
      `${this.baseUrl}/refunds/${refundId}/chat/`,
      party ? { party } : {},
      { withCredentials: true }
    );
  }

  openConsoleRefundChat(
    refundId: number,
    party: 'renter' | 'owner'
  ): Observable<{ ok: boolean; conversation_id: number; url: string }> {
    return this.http.post<{ ok: boolean; conversation_id: number; url: string }>(
      `${this.baseUrl}/console/refunds/${refundId}/chat/`,
      { party },
      { withCredentials: true }
    );
  }

  sendMessage(id: number, body: string): Observable<{ message: ChatMessage }> {
    return this.http.post<{ message: ChatMessage }>(
      `${this.baseUrl}/conversations/${id}/messages/`,
      { body },
      { withCredentials: true }
    );
  }
}
