import { Component, inject, signal } from '@angular/core';
import { Router, RouterLink, RouterLinkActive } from '@angular/router';
import { CommonModule } from '@angular/common';
import { AuthService } from '../../services/auth.service';
import { NotificationService } from '../../services/notification.service';
import { AppNotification } from '../../models';
import { ThemeService } from '../../services/theme.service';
import { LanguageService } from '../../services/language.service';

@Component({
  selector: 'app-navbar',
  imports: [CommonModule, RouterLink, RouterLinkActive],
  templateUrl: './navbar.html',
})
export class NavbarComponent {
  readonly auth = inject(AuthService);
  readonly notifService = inject(NotificationService);
  readonly themeService = inject(ThemeService);
  readonly language = inject(LanguageService);
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

  openNotification(notification: AppNotification): void {
    this.isNotifMenuOpen.set(false);
    if (!notification.read) {
      this.notifService.toggleRead(notification.id).subscribe();
    }
    const link = notification.link || '';
    const bookingMatch = link.match(/(?:rent|owner)\/bookings\/(?:#?BK-)?(\d+)/i);
    if (bookingMatch) {
      const base = this.auth.isOwner() ? '/owner/bookings' : '/bookings';
      this.router.navigate([base, bookingMatch[1]]);
    } else if (link && link !== '/notifications/') {
      this.router.navigateByUrl(link);
    } else {
      this.router.navigate(['/notifications']);
    }
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
