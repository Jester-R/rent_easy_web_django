import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { NotificationService } from '../../services/notification.service';
import { AppNotification } from '../../models';
import { IconComponent } from '../../components/icon/icon';
import { AuthService } from '../../services/auth.service';
import { LanguageService } from '../../services/language.service';

@Component({
  selector: 'app-notifications',
  imports: [CommonModule, IconComponent],
  templateUrl: './notifications.html',
})
export class NotificationsComponent implements OnInit {
  readonly language = inject(LanguageService);
  private readonly notificationService = inject(NotificationService);
  private readonly router = inject(Router);
  private readonly auth = inject(AuthService);

  notifications = signal<AppNotification[]>([]);
  isLoading = signal(true);

  ngOnInit(): void {
    this.loadNotifications();
  }

  loadNotifications(): void {
    this.isLoading.set(true);
    this.notificationService.getNotifications().subscribe({
      next: (res) => {
        this.notifications.set(res.notifications);
        this.isLoading.set(false);
      },
      error: () => this.isLoading.set(false),
    });
  }

  toggleRead(id: number): void {
    this.notificationService.toggleRead(id).subscribe({
      next: (res) => {
        this.notifications.update((list) =>
          list.map((n) => (n.id === id ? { ...n, read: res.read } : n))
        );
      },
    });
  }

  openNotification(notification: AppNotification): void {
    if (!notification.read) {
      this.notificationService.toggleRead(notification.id).subscribe({
        next: () => this.updateReadState(notification.id, true),
      });
    }

    const link = notification.link || '';
    const bookingMatch = link.match(/(?:rent|owner)\/bookings\/(?:#?BK-)?(\d+)/i);
    if (bookingMatch) {
      const base = this.auth.isOwner() ? '/owner/bookings' : '/bookings';
      this.router.navigate([base, bookingMatch[1]]);
    } else if (link && link !== '/notifications/') {
      this.router.navigateByUrl(link);
    }
  }

  private updateReadState(id: number, read: boolean): void {
    this.notifications.update((list) =>
      list.map((n) => (n.id === id ? { ...n, read } : n))
    );
  }

  markAllRead(): void {
    this.notificationService.readAll().subscribe({
      next: () => {
        this.notifications.update((list) =>
          list.map((n) => ({ ...n, read: true }))
        );
      },
    });
  }
}
