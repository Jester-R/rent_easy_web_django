import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { PropertyService } from '../../../services/property.service';
import { Property } from '../../../models';
import { LanguageService } from '../../../services/language.service';

@Component({
  selector: 'app-owner-properties',
  imports: [CommonModule, RouterLink],
  templateUrl: './owner-list.html',
})
export class OwnerPropertiesComponent implements OnInit {
  readonly language = inject(LanguageService);
  private readonly propertyService = inject(PropertyService);

  properties = signal<Property[]>([]);
  isLoading = signal(true);
  successMessage = signal<string | null>(null);

  ngOnInit(): void {
    this.loadProperties();
  }

  loadProperties(): void {
    this.isLoading.set(true);
    this.propertyService.getOwnerProperties().subscribe({
      next: (res) => {
        this.properties.set(res.properties);
        this.isLoading.set(false);
      },
      error: () => this.isLoading.set(false),
    });
  }

  deleteProperty(id: number): void {
    if (!confirm('Are you sure you want to delete this listing?')) return;

    this.propertyService.deleteProperty(id).subscribe({
      next: () => {
        this.successMessage.set('Listing removed successfully.');
        this.loadProperties();
      },
    });
  }
}
