import {
  AfterViewInit,
  Component,
  ElementRef,
  OnDestroy,
  PLATFORM_ID,
  effect,
  inject,
  input,
  output,
  viewChild,
} from '@angular/core';
import { isPlatformBrowser } from '@angular/common';
import { loadLeaflet } from '../../shared/leaflet';

@Component({
  selector: 'app-leaflet-map',
  template: `
    <div #host class="leaflet-host" [style.height.px]="height()"></div>
  `,
  styles: [
    `
      .leaflet-host {
        width: 100%;
        border-radius: 1rem;
        overflow: hidden;
        background: #e5e7eb;
        z-index: 0;
      }
      .leaflet-host:empty::after {
        content: 'Loading map…';
        display: flex;
        height: 100%;
        align-items: center;
        justify-content: center;
        color: #6b7280;
        font-size: 0.875rem;
      }
    `,
  ],
})
export class LeafletMapComponent implements AfterViewInit, OnDestroy {
  readonly latitude = input<number | null>(null);
  readonly longitude = input<number | null>(null);
  readonly zoom = input<number>(14);
  readonly height = input<number>(220);
  readonly interactive = input<boolean>(false);
  readonly coordinatesChange = output<{ latitude: number; longitude: number }>();

  private readonly host = viewChild.required<ElementRef<HTMLDivElement>>('host');
  private readonly platformId = inject(PLATFORM_ID);

  private L: any = null;
  private map: any = null;
  private marker: any = null;
  private lastEmit = '';

  constructor() {
    effect(() => {
      const lat = this.latitude();
      const lng = this.longitude();
      this.syncMarker(lat, lng);
    });
  }

  ngAfterViewInit(): void {
    if (!isPlatformBrowser(this.platformId)) return;
    loadLeaflet()
      .then((L) => this.initMap(L))
      .catch(() => undefined);
  }

  ngOnDestroy(): void {
    this.map?.remove();
    this.map = null;
  }

  private initMap(L: any): void {
    this.L = L;
    const lat = this.latitude();
    const lng = this.longitude();
    const hasCoords = typeof lat === 'number' && typeof lng === 'number';
    const center: [number, number] = hasCoords ? [lat!, lng!] : [11.5564, 104.9282];

    this.map = L.map(this.host().nativeElement, {
      zoomControl: this.interactive(),
      attributionControl: true,
      scrollWheelZoom: this.interactive(),
    }).setView(center, this.zoom());

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap contributors',
    }).addTo(this.map);

    const icon = L.divIcon({
      className: 'renteasy-map-pin',
      html: `<div style="width:26px;height:26px;border-radius:50% 50% 50% 0;transform:rotate(-45deg);background:#dc2626;border:3px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,.35)"></div>`,
      iconSize: [26, 26],
      iconAnchor: [13, 26],
    });
    this.marker = L.marker(center, { icon, draggable: this.interactive() }).addTo(this.map);

    if (this.interactive()) {
      this.map.on('click', (event: any) => {
        const point = event.latlng;
        this.marker.setLatLng(point);
        this.emitCoordinates(point.lat, point.lng);
      });
      this.marker.on('dragend', () => {
        const point = this.marker.getLatLng();
        this.emitCoordinates(point.lat, point.lng);
      });
      if (!hasCoords) {
        this.emitCoordinates(center[0], center[1]);
      }
    }

    setTimeout(() => this.map?.invalidateSize(), 0);
  }

  private syncMarker(lat: number | null, lng: number | null): void {
    if (!this.map || !this.marker || lat == null || lng == null) return;
    const point: [number, number] = [lat, lng];
    this.marker.setLatLng(point);
    if (!this.map.getBounds().contains(point)) {
      this.map.setView(point, this.zoom());
    }
  }

  private emitCoordinates(latitude: number, longitude: number): void {
    const key = `${latitude.toFixed(6)},${longitude.toFixed(6)}`;
    if (key === this.lastEmit) return;
    this.lastEmit = key;
    this.coordinatesChange.emit({ latitude, longitude });
  }
}
