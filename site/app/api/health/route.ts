import { NextResponse } from 'next/server';

export async function GET() {
  return NextResponse.json({
    status: 'healthy',
    service: 'brocc-site-api',
    timestamp: new Date().toISOString()
  });
}
