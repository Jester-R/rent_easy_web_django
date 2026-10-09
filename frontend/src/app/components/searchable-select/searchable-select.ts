import {
  Component,
  ElementRef,
  HostListener,
  Input,
  forwardRef,
  signal,
  computed,
  inject,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { ControlValueAccessor, NG_VALUE_ACCESSOR } from '@angular/forms';

export interface SelectOption {
  value: string;
  label: string;
}

@Component({
  selector: 'app-searchable-select',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './searchable-select.html',
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => SearchableSelectComponent),
      multi: true,
    },
  ],
})
export class SearchableSelectComponent implements ControlValueAccessor {
  private readonly host = inject(ElementRef<HTMLElement>);

  @Input() options: SelectOption[] = [];
  @Input() placeholder = '';
  @Input() searchPlaceholder = 'Search...';
  @Input() ariaLabel = '';

  readonly value = signal<string>('');
  readonly disabled = signal(false);
  readonly open = signal(false);
  readonly query = signal('');
  readonly activeIndex = signal(0);

  private onChange: (value: string) => void = () => {};
  private onTouched: () => void = () => {};

  readonly filtered = computed(() => {
    const q = this.query().trim().toLowerCase();
    if (!q) return this.options;
    return this.options.filter((o) => o.label.toLowerCase().includes(q));
  });

  readonly selectedLabel = computed(
    () => this.options.find((o) => o.value === this.value())?.label ?? ''
  );

  writeValue(value: string): void {
    this.value.set(value ?? '');
  }

  registerOnChange(fn: (value: string) => void): void {
    this.onChange = fn;
  }

  registerOnTouched(fn: () => void): void {
    this.onTouched = fn;
  }

  setDisabledState(isDisabled: boolean): void {
    this.disabled.set(isDisabled);
  }

  toggle(): void {
    if (this.disabled()) return;
    this.open.update((v) => !v);
    if (this.open()) {
      this.query.set('');
      this.activeIndex.set(Math.max(0, this.filtered().findIndex((o) => o.value === this.value())));
    } else {
      this.onTouched();
    }
  }

  choose(option: SelectOption): void {
    this.value.set(option.value);
    this.onChange(option.value);
    this.onTouched();
    this.open.set(false);
  }

  onSearch(value: string): void {
    this.query.set(value);
    this.activeIndex.set(0);
  }

  onKeydown(event: KeyboardEvent): void {
    if (this.disabled()) return;
    const items = this.filtered();
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      this.activeIndex.update((i) => Math.min(i + 1, items.length - 1));
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      this.activeIndex.update((i) => Math.max(i - 1, 0));
    } else if (event.key === 'Enter') {
      event.preventDefault();
      const item = items[this.activeIndex()];
      if (item) this.choose(item);
    } else if (event.key === 'Escape') {
      this.open.set(false);
    }
  }

  @HostListener('document:click', ['$event'])
  onDocumentClick(event: MouseEvent): void {
    if (this.open() && !this.host.nativeElement.contains(event.target as Node)) {
      this.open.set(false);
      this.onTouched();
    }
  }
}
