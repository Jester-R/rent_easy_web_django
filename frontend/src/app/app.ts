import { Component, inject, signal } from '@angular/core';
import { NavigationEnd, Router } from '@angular/router';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { CommonModule } from '@angular/common';
import { AuthService } from './services/auth.service';
import { NavbarComponent } from './components/navbar/navbar';
import { FooterComponent } from './components/footer/footer';
import { IconComponent } from './components/icon/icon';
import { LanguageService } from './services/language.service';

@Component({
  selector: 'app-root',
  imports: [CommonModule, RouterOutlet, RouterLink, RouterLinkActive, NavbarComponent, FooterComponent, IconComponent],
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App {
  readonly auth = inject(AuthService);
  readonly language = inject(LanguageService);
  private readonly router = inject(Router);
  readonly adminMoreOpen = signal(false);
  readonly paymentsMenuOpen = signal(false);

  constructor() {
    this.router.events.subscribe((event) => {
      if (event instanceof NavigationEnd) {
        this.paymentsMenuOpen.set(
          event.urlAfterRedirects.startsWith('/console/payments'),
        );
      }
    });
  }

  closeAdminMore(): void {
    this.adminMoreOpen.set(false);
  }

  logout(): void {
    this.auth.logout().subscribe({
      next: () => this.router.navigate(['/']),
    });
  }
}
