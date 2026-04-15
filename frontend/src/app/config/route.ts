import { NextResponse } from 'next/server'

function isLocalApiUrl(value: string): boolean {
  try {
    const url = new URL(value)
    return url.hostname === 'localhost' || url.hostname === '127.0.0.1'
  } catch {
    return false
  }
}

/**
 * Runtime Configuration Endpoint
 *
 * En este fork, el comportamiento por defecto debe favorecer uso estrictamente
 * local. Por eso:
 *
 * - solo se acepta una API_URL explícita si apunta a localhost / 127.0.0.1;
 * - en caso contrario se devuelve cadena vacía para que el frontend use rutas
 *   relativas locales a través de los rewrites de Next.js;
 * - no se autodetectan hosts ni cabeceras pensadas para despliegues en red.
 */
export async function GET() {
  const envApiUrl = process.env.API_URL || process.env.NEXT_PUBLIC_API_URL

  if (envApiUrl && isLocalApiUrl(envApiUrl)) {
    return NextResponse.json({
      apiUrl: envApiUrl,
    })
  }

  return NextResponse.json({
    apiUrl: '',
  })
}
