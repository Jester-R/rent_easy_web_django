import { Component, inject, input, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { ConsoleService } from '../../../services/console.service';
import { IconComponent } from '../../../components/icon/icon';
import { Booking, ConsolePropertyItem, ConsoleUserItem } from '../../../models';
import { prettyDate } from '../../../shared/ui';

@Component({
  selector: 'app-console-booking-form',
  imports: [CommonModule, ReactiveFormsModule, RouterLink, IconComponent],
  templateUrl: './console-booking-form.html',
})
export class ConsoleBookingFormComponent implements OnInit {
  readonly id = input<string>();

  private readonly fb = inject(FormBuilder);
  private readonly console = inject(ConsoleService);
  private readonly router = inject(Router);

  readonly prettyDate = prettyDate;

  isEdit = signal(false);
  isLoading = signal(true);
  isSaving = signal(false);
  submitted = signal(false);
  error = signal<string | null>(null);
  booking = signal<Booking | null>(null);
  properties = signal<ConsolePropertyItem[]>([]);
  renters = signal<ConsoleUserItem[]>([]);
  owners = signal<ConsoleUserItem[]>([]);

  form = this.fb.group({
    property: [null as number | null],
    renter: [null as number | null],
    owner: [null as number | null],
    status: ['Pending'],
    monthly_rent: [0, [Validators.required, Validators.min(0)]],
    lease_months: [12, [Validators.required, Validators.min(1), Validators.max(120)]],
    move_in_date: [''],
    note: [''],
  });

  ngOnInit(): void {
    if (this.id()) {
      this.isEdit.set(true);
      this.loadBooking(Number(this.id()));
    } else {
      this.isLoading.set(false);
      this.loadDropdowns();
    }
  }

  loadDropdowns(): void {
    this.console.getProperties({}).subscribe({
      next: (res) => this.properties.set(res.properties),
    });
    this.console.getUsers({ role: 'renter' }).subscribe({
      next: (res) => this.renters.set(res.users),
    });
    this.console.getUsers({ role: 'owner' }).subscribe({
      next: (res) => this.owners.set(res.users),
    });
  }

  loadBooking(id: number): void {
    this.isLoading.set(true);
    this.console.getBookings({}).subscribe({
      next: (res) => {
        this.isLoading.set(false);
        const b = res.bookings.find((x) => x.id === id);
        if (!b) {
          this.error.set('Booking not found.');
          return;
        }
        this.booking.set(b);
        this.form.patchValue({
          status: b.status,
          monthly_rent: b.monthly_rent,
          lease_months: b.lease_months,
          move_in_date: (b.move_in_date || '').slice(0, 10),
          note: b.note,
        });
      },
      error: () => {
        this.isLoading.set(false);
        this.error.set('Failed to load booking.');
      },
    });
  }

  onSubmit(): void {
    this.submitted.set(true);
    this.error.set(null);
    if (this.id()) {
      this.saveEdit();
    } else {
      this.saveCreate();
    }
  }

  saveCreate(): void {
    const v = this.form.value;
    if (!v.property || !v.renter) {
      this.error.set('Property and renter are required.');
      return;
    }
    this.isSaving.set(true);
    const payload: Record<string, unknown> = {
      property: Number(v.property),
      renter: Number(v.renter),
      status: v.status || 'Pending',
      monthly_rent: Number(v.monthly_rent) || 0,
      lease_months: Number(v.lease_months) || 12,
      move_in_date: v.move_in_date || '',
      note: v.note || '',
    };
    if (v.owner) payload['owner'] = Number(v.owner);
    this.console.createBooking(payload).subscribe({
      next: () => {
        this.isSaving.set(false);
        this.router.navigate(['/console/bookings']);
      },
      error: (err) => {
        this.isSaving.set(false);
        this.mapError(err);
      },
    });
  }

  saveEdit(): void {
    const v = this.form.value;
    this.isSaving.set(true);
    const payload: Record<string, unknown> = {
      status: v.status || 'Pending',
      monthly_rent: Number(v.monthly_rent) || 0,
      lease_months: Number(v.lease_months) || 12,
      move_in_date: v.move_in_date || '',
      note: v.note || '',
    };
    this.console.updateBooking(Number(this.id()), payload).subscribe({
      next: () => {
        this.isSaving.set(false);
        this.router.navigate(['/console/bookings']);
      },
      error: (err) => {
        this.isSaving.set(false);
        this.mapError(err);
      },
    });
  }

  private mapError(err: unknown): void {
    const key = (err as { error?: { detail?: string } }).error?.detail;
    const messages: Record<string, string> = {
      property_and_renter_required: 'Property and renter are required.',
      invalid_status: 'Invalid status.',
      invalid_date: 'Move-in date must be a valid date.',
    };
    this.error.set((key && messages[key]) || 'Failed to save booking.');
  }
}