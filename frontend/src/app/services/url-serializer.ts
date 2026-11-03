import { Injectable } from '@angular/core';
import { DefaultUrlSerializer, UrlTree } from '@angular/router';

@Injectable({
  providedIn: 'root',
})
export class TrailingSlashUrlSerializer extends DefaultUrlSerializer {
  override parse(url: string): UrlTree {
    const [pathAndQuery, hash] = url.split('#');
    const [pathname, search] = pathAndQuery.split('?');
    const cleanedPath =
      pathname.length > 1 && pathname.endsWith('/')
        ? pathname.replace(/\/+$/, '')
        : pathname;
    const reconstructed =
      cleanedPath + (search ? `?${search}` : '') + (hash ? `#${hash}` : '');
    return super.parse(reconstructed);
  }
}
