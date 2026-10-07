import { Component, inject, signal } from '@angular/core';
import { Router, RouterLink, RouterLinkActive } from '@angular/router';
import { CommonModule } from '@angular/common';
import { AuthService } from '../../services/auth.service';
import { NotificationService } from '../../services/notification.service';
import { AppNotification } from '../../models';
import { ThemeService } from '../../services/theme.service';

@Component({
  selector: 'app-navbar',
  imports: [CommonModule, RouterLink, RouterLinkActive],
  templateUrl: './navbar.html',
})
export class NavbarComponent {
  readonly auth = inject(AuthService);
  readonly notifService = inject(NotificationService);
  readonly themeService = inject(ThemeService);
  private readonly router = inject(Router);

  isMobileMenuOpen = signal(false);
  isProfileMenuOpen = signal(false);
  isNotifMenuOpen = signal(false);
  notifications = signal<AppNotification[]>([]);

  toggleMobileMenu(): void {
    this.isMobileMenuOpen.update((v) => !v);
  }

  toggleProfileMenu(): void {
    this.isProfileMenuOpen.update((v) => !v);
    if (this.isProfileMenuOpen()) {
      this.isNotifMenuOpen.set(false);
    }
  }

  toggleNotifMenu(): void {
    this.isNotifMenuOpen.update((v) => !v);
    if (this.isNotifMenuOpen()) {
      this.isProfileMenuOpen.set(false);
      this.fetchNotificationsPreview();
    }
  }

  fetchNotificationsPreview(): void {
    this.notifService.getPreview().subscribe({
      next: (res) => {
        this.notifications.set(res.items || []);
      },
    });
  }

  markAllRead(): void {
    this.notifService.readAll().subscribe(() => {
      this.fetchNotificationsPreview();
    });
  }

  logout(): void {
    this.auth.logout().subscribe({
      next: () => {
        this.isProfileMenuOpen.set(false);
        this.router.navigate(['/']);
      },
    });
  }
}
