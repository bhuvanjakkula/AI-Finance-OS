import {defineConfig} from 'vite';

// Loopback preview uses one browser origin; production nginx supplies /api.
const proxy={'/api':{target:process.env.FINANCE_API_INTERNAL_URL||'http://127.0.0.1:8000',changeOrigin:false,rewrite:path=>path.replace(/^\/api/,'')}};
export default defineConfig({server:{proxy},preview:{proxy}});
