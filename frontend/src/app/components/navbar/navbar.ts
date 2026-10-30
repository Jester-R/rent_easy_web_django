import { Component, effect, inject, signal, OnDestroy, PLATFORM_ID } from '@angular/core';
import { Router, RouterLink, RouterLinkActive } from '@angular/router';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { AuthService } from '../../services/auth.service';
import { NotificationService } from '../../services/notification.service';
import { AppNotification } from '../../models';
import { ThemeService } from '../../services/theme.service';
import { LanguageService } from '../../services/language.service';
import { notificationIcon, notificationText } from '../../shared/ui';
import { IconComponent } from '../icon/icon';

@Component({
  selector: 'app-navbar',
  imports: [CommonModule, RouterLink, RouterLinkActive, IconComponent],
  templateUrl: './navbar.html',
})
export class NavbarComponent implements OnDestroy {
  readonly auth = inject(AuthService);
  readonly notifService = inject(NotificationService);
  readonly themeService = inject(ThemeService);
  readonly language = inject(LanguageService);
  readonly notificationText = notificationText;
  readonly notificationIcon = notificationIcon;
  private readonly router = inject(Router);
  private readonly platformId = inject(PLATFORM_ID);

  isMobileMenuOpen = signal(false);
  isProfileMenuOpen = signal(false);
  isNotifMenuOpen = signal(false);
  notifications = signal<AppNotification[]>([]);

  constructor() {
    if (!isPlatformBrowser(this.platformId)) return;

    // Keep one SSE connection per signed-in tab instead of polling the badge.
    effect(() => {
      const user = this.auth.currentUser();
      if (user) {
        this.notifService.connect();
        this.fetchNotificationsPreview();
      } else {
        this.notifService.disconnect();
        this.notifService.unreadCount.set(0);
        this.notifService.preview.set([]);
        this.notifications.set([]);
      }
    });

    // Keep the preview current from the live notification stream, whether or
    // not the dropdown is open. Opening it only reveals the already loaded rows.
    effect(() => {
      const incoming = this.notifService.incoming();
      if (!incoming) return;
      this.fetchNotificationsPreview();
    });

    effect(() => {
      this.notifications.set(this.notifService.preview());
    });
  }

  ngOnDestroy(): void {
    this.notifService.disconnect();
  }

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
      // Refresh on open as well as preloading after sign-in. This covers a
      // slow initial session check and keeps the visible dropdown current.
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
    this.notifService.readAll().subscribe({
      next: () => this.fetchNotificationsPreview(),
    });
  }

  /** "Switch to <other language>" rendered in the target language. */
  switchTitle(): string {
    const other = this.language.other();
    return this.language.tIn(other, other === 'km' ? 'navbar.switchToKhmer' : 'navbar.switchToEnglish');
  }

  /** Target language name shown on the toggle, rendered in the target language. */
  switchName(): string {
    const other = this.language.other();
    return this.language.tIn(other, other === 'km' ? 'navbar.langKhmer' : 'navbar.langEnglish');
  }

  openNotification(notification: AppNotification): void {
    this.isNotifMenuOpen.set(false);
    if (!notification.read) {
      this.notifService.toggleRead(notification.id).subscribe({
        next: () => {
          this.notifications.update((list) =>
            list.map((n) => (n.id === notification.id ? { ...n, read: true } : n))
          );
          this.fetchNotificationsPreview();
        },
        error: () => undefined,
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
