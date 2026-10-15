import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { NotificationService } from '../../services/notification.service';
import { AppNotification } from '../../models';
import { IconComponent } from '../../components/icon/icon';
import { DataPaginationComponent } from '../../components/data-pagination/data-pagination';
import { AuthService } from '../../services/auth.service';
import { LanguageService } from '../../services/language.service';
import { notificationIcon, notificationText } from '../../shared/ui';

@Component({
  selector: 'app-notifications',
  imports: [CommonModule, IconComponent, DataPaginationComponent],
  templateUrl: './notifications.html',
})
export class NotificationsComponent implements OnInit {
  readonly language = inject(LanguageService);
  readonly notificationText = notificationText;
  readonly notificationIcon = notificationIcon;
  private readonly notificationService = inject(NotificationService);
  private readonly router = inject(Router);
  private readonly auth = inject(AuthService);

  notifications = signal<AppNotification[]>([]);
  total = signal(0);
  page = signal(1);
  readonly pageSize = 25;
  isLoading = signal(true);

  ngOnInit(): void {
    this.loadNotifications();
  }

  loadNotifications(): void {
    this.isLoading.set(true);
    this.notificationService.getNotifications(this.page(), this.pageSize).subscribe({
      next: (res) => {
        this.notifications.set(res.notifications);
        this.total.set(res.total);
        this.page.set(res.page);
        this.isLoading.set(false);
      },
      error: () => this.isLoading.set(false),
    });
  }

  changePage(page: number): void {
    this.page.set(page);
    this.loadNotifications();
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
    const paymentMatch = link.match(/(?:rent\/)?payments\/(\d+)/i);
    const bookingMatch = link.match(/(?:rent|owner)\/bookings\/(?:#?BK-)?(\d+)/i);
    if (paymentMatch) {
      this.router.navigate(['/payments', paymentMatch[1]]);
    } else if (bookingMatch) {
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
