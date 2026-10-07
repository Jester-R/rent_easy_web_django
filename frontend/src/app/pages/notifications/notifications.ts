import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NotificationService } from '../../services/notification.service';
import { AppNotification } from '../../models';
import { IconComponent } from '../../components/icon/icon';

@Component({
  selector: 'app-notifications',
  imports: [CommonModule, IconComponent],
  templateUrl: './notifications.html',
})
export class NotificationsComponent implements OnInit {
  private readonly notificationService = inject(NotificationService);

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
