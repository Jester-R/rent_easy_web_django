import { Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { IconComponent } from '../../../components/icon/icon';
import { AuthService } from '../../../services/auth.service';

@Component({
  selector: 'app-denied',
  imports: [RouterLink, IconComponent],
  templateUrl: './denied.html',
})
export class DeniedComponent {
  readonly auth = inject(AuthService);
}