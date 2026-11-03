import { Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { AuthService } from '../../../services/auth.service';

@Component({
  selector: 'app-role-select',
  imports: [CommonModule],
  templateUrl: './role-select.html',
})
export class RoleSelectComponent {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  selectedRole = signal<'renter' | 'owner'>('renter');
  isLoading = signal(false);
  errorMessage = signal<string | null>(null);

  selectRole(role: 'renter' | 'owner'): void {
    this.selectedRole.set(role);
  }

  submitRole(): void {
    this.isLoading.set(true);
    this.errorMessage.set(null);

    this.auth.selectRole(this.selectedRole()).subscribe({
      next: (res) => {
        this.isLoading.set(false);
        if (res.status === 'pending_approval' || res.redirect?.includes('pending=1')) {
          this.router.navigate(['/register'], { queryParams: { pending: '1' } });
          return;
        }
        const rawDest = res.redirect || res.home_url || '';
        const dest = rawDest.length > 1 && rawDest.endsWith('/') ? rawDest.replace(/\/+$/, '') : rawDest;
        if (dest && dest.startsWith('/') && !dest.startsWith('/login')) {
          this.router.navigateByUrl(dest);
        } else if (this.selectedRole() === 'owner') {
          this.router.navigate(['/owner']);
        } else {
          this.router.navigate(['/rent']);
        }
      },
      error: (err) => {
        this.isLoading.set(false);
        const detail = err.error?.detail;
        if (detail === 'no_pending_registration') {
          this.errorMessage.set('No pending registration found. Please sign in again with Google.');
        } else {
          this.errorMessage.set('Failed to set role. Please try again.');
        }
      },
    });
  }
}
