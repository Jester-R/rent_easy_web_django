import {
  AngularNodeAppEngine,
  createNodeRequestHandler,
  isMainModule,
  writeResponseToNodeResponse,
} from '@angular/ssr/node';

import http from 'node:http';
import https from 'node:https';
import { createReadStream } from 'node:fs';
import { stat } from 'node:fs/promises';
import { join, resolve, extname, sep } from 'node:path';
import type {
  IncomingMessage,
  ServerResponse,
} from 'node:http';

import {
  ɵsetAngularAppEngineManifest as setAngularAppEngineManifest,
} from '@angular/ssr';
import angularAppEngineManifest from './angular-app-engine-manifest.mjs';

setAngularAppEngineManifest(angularAppEngineManifest);

// Configuration
const PORT = Number(process.env['PORT'] || 4200);
const BACKEND_URL =
  process.env['BACKEND_URL'] || 'http://127.0.0.1:8000';

const backendTarget = new URL(BACKEND_URL);

if (!['http:', 'https:'].includes(backendTarget.protocol)) {
  throw new Error('BACKEND_URL must use HTTP or HTTPS');
}

const browserDistFolder = resolve(
  join(import.meta.dirname, '../browser'),
);

const angularApp = new AngularNodeAppEngine();

// Headers that should not be forwarded by the proxy.
const HOP_BY_HOP = new Set([
  'connection',
  'keep-alive',
  'proxy-authenticate',
  'proxy-authorization',
  'te',
  'trailer',
  'transfer-encoding',
  'upgrade',
]);

function removeHopByHopHeaders(
  headers: Record<string, string | string[] | undefined>,
) {
  // Connection headers can nominate additional hop-by-hop headers.
  const connection = headers['connection'];

  if (typeof connection === 'string') {
    for (const name of connection.split(',')) {
      headers[name.trim().toLowerCase()] = undefined;
    }
  }

  for (const name of HOP_BY_HOP) {
    delete headers[name];
  }

  return headers;
}

// MIME types for static assets.
const MIME_TYPES: Record<string, string> = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.mjs': 'application/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.webp': 'image/webp',
  '.ico': 'image/x-icon',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.ttf': 'font/ttf',
  '.wasm': 'application/wasm',
  '.txt': 'text/plain; charset=utf-8',
  '.xml': 'application/xml',
};

// Static file handler.
async function serveStatic(
  req: IncomingMessage,
  res: ServerResponse,
): Promise<boolean> {
  if (req.method !== 'GET' && req.method !== 'HEAD') {
    return false;
  }

  let pathname: string;

  try {
    pathname = decodeURIComponent(
      new URL(req.url || '/', 'http://localhost').pathname,
    );
  } catch {
    res.writeHead(400);
    res.end('Bad Request');
    return true;
  }

  const filePath = resolve(
    browserDistFolder,
    `.${pathname}`,
  );

  // Prevent directory traversal.
  if (
    filePath !== browserDistFolder &&
    !filePath.startsWith(browserDistFolder + sep)
  ) {
    res.writeHead(403);
    res.end('Forbidden');
    return true;
  }

  try {
    const fileStat = await stat(filePath);

    // Do not serve directories or redirect directory requests.
    if (!fileStat.isFile()) {
      return false;
    }

    const contentType =
      MIME_TYPES[extname(filePath).toLowerCase()] ||
      'application/octet-stream';

    res.writeHead(200, {
      'Content-Type': contentType,
      'Content-Length': fileStat.size,
      'Last-Modified': fileStat.mtime.toUTCString(),
      'Cache-Control': 'public, max-age=31536000',
    });

    if (req.method === 'HEAD') {
      res.end();
      return true;
    }

    const stream = createReadStream(filePath);

    stream.on('error', (error) => {
      console.error('Static file error:', error);

      if (!res.headersSent) {
        res.writeHead(500);
        res.end('Internal Server Error');
      } else {
        res.destroy(error);
      }
    });

    stream.pipe(res);

    return true;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') {
      return false;
    }

    throw error;
  }
}

// API reverse proxy.
function proxyRequest(
  req: IncomingMessage,
  res: ServerResponse,
): void {
  const headers = removeHopByHopHeaders({
    ...req.headers,
    host: backendTarget.host,
  });

  const transport =
    backendTarget.protocol === 'https:' ? https : http;

  // Remove /api prefix while preserving query parameters.
  const path = (req.url || '/').replace(
    /^\/api(?=\/|$)/,
    '',
  ) || '/';

  const proxyReq = transport.request(
    {
      protocol: backendTarget.protocol,
      hostname: backendTarget.hostname,
      port: backendTarget.port || undefined,
      method: req.method,
      path,
      headers,
    },
    (proxyRes) => {
      const responseHeaders = removeHopByHopHeaders({
        ...proxyRes.headers,
      });

      res.writeHead(
        proxyRes.statusCode || 502,
        responseHeaders,
      );

      proxyRes.pipe(res);
    },
  );

  proxyReq.on('error', (error) => {
    console.error('API proxy error:', error);

    if (!res.headersSent) {
      res.writeHead(502, {
        'Content-Type': 'application/json',
      });

      res.end(
        JSON.stringify({
          detail: 'API backend unreachable',
          error: error.message,
        }),
      );
    } else {
      res.destroy(error);
    }
  });

  req.on('aborted', () => {
    proxyReq.destroy();
  });

  req.pipe(proxyReq);
}

// Main Node.js request handler.
const handler = async (
  req: IncomingMessage,
  res: ServerResponse,
  next: (err?: unknown) => void,
): Promise<void> => {
  try {
    const pathname = new URL(
      req.url || '/',
      'http://localhost',
    ).pathname;

    // 1. API proxy.
    if (
      pathname === '/api' ||
      pathname.startsWith('/api/')
    ) {
      proxyRequest(req, res);
      return;
    }

    // 2. Static files.
    if (await serveStatic(req, res)) {
      return;
    }

    // 3. Angular SSR.
    const response = await angularApp.handle(req);

    if (response) {
      await writeResponseToNodeResponse(response, res);
    } else {
      next();
    }
  } catch (error) {
    next(error);
  }
};

// Native HTTP server.
const server = http.createServer((req, res) => {
  const next = (error?: unknown) => {
    if (error) {
      console.error(error);

      if (!res.headersSent) {
        res.writeHead(500, {
          'Content-Type': 'text/plain',
        });

        res.end('Internal Server Error');
      } else {
        res.destroy(
          error instanceof Error ? error : undefined,
        );
      }

      return;
    }

    if (!res.headersSent) {
      res.writeHead(404);
      res.end('Not Found');
    }
  };

  void handler(req, res, next).catch(next);
});

// Start server.
if (
  isMainModule(import.meta.url) ||
  process.env['pm_id']
) {
  server.listen(PORT, () => {
    console.log(
      `Node.js server listening on http://localhost:${PORT}`,
    );

    console.log(`Backend: ${BACKEND_URL}`);
    console.log(`Frontend: ${browserDistFolder}`);
  });
}

// Angular CLI / Firebase request handler.
export const reqHandler =
  createNodeRequestHandler(handler);

export default reqHandler;
