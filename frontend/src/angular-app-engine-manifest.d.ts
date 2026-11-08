declare module '*.mjs' {
  const manifest: Parameters<
    typeof import('@angular/ssr')['ɵsetAngularAppEngineManifest']
  >[0];
  export default manifest;
}
