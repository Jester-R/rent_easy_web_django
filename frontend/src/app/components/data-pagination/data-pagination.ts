import { Component, computed, inject, input, output } from '@angular/core';
import { LanguageService } from '../../services/language.service';

@Component({
  selector: 'app-data-pagination',
  template: `
    @if (total() > pageSize()) {
      <nav class="flex flex-wrap items-center justify-between gap-3 py-3" aria-label="Pagination">
        <span class="text-[12px] text-ink-3">{{ language.t('app.paginationRange', { start: start(), end: end(), total: total() }) }}</span>
        <div class="flex items-center gap-2">
          <button type="button" class="btn btn-outline btn-sm" [disabled]="page() <= 1" (click)="pageChange.emit(page() - 1)">{{ language.t('app.previous') }}</button>
          <span class="text-[12px] font-semibold tabular-nums">{{ page() }} / {{ pages() }}</span>
          <button type="button" class="btn btn-outline btn-sm" [disabled]="page() >= pages()" (click)="pageChange.emit(page() + 1)">{{ language.t('app.next') }}</button>
        </div>
      </nav>
    }
  `,
})
export class DataPaginationComponent {
  readonly language = inject(LanguageService);
  readonly page = input.required<number>();
  readonly pageSize = input.required<number>();
  readonly total = input.required<number>();
  readonly pageChange = output<number>();
  readonly pages = computed(() => Math.max(1, Math.ceil(this.total() / this.pageSize())));
  readonly start = computed(() => this.total() === 0 ? 0 : (this.page() - 1) * this.pageSize() + 1);
  readonly end = computed(() => Math.min(this.page() * this.pageSize(), this.total()));
}
