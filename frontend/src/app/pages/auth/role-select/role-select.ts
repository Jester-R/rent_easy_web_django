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
      next: () => {
        this.isLoading.set(false);
        this.router.navigate(['/login']);
      },
      error: () => {
        this.isLoading.set(false);
        this.errorMessage.set('Failed to set role. Please try logging in.');
      },
    });
  }
}
