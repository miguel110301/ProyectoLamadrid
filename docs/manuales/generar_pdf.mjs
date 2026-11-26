// Genera los PDF de los manuales a partir de los HTML de esta carpeta (tamaño carta, con pie de página).
// Requiere Google Chrome y puppeteer-core:   npm i puppeteer-core@23   (en cualquier carpeta de trabajo)
// Uso:   node generar_pdf.mjs            (desde esa carpeta de trabajo, pasando la ruta si hace falta)
//        node /ruta/a/docs/manuales/generar_pdf.mjs
import puppeteer from 'puppeteer-core';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const AQUI = dirname(fileURLToPath(import.meta.url));
const CHROME = process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const MANUALES = [
  ['manual-de-usuario.html', 'Manual de usuario - Control Maestro TvUAQ.pdf', 'Manual de usuario'],
  ['manual-tecnico.html', 'Manual técnico - Control Maestro TvUAQ.pdf', 'Manual técnico'],
];

const nav = await puppeteer.launch({ executablePath: CHROME, headless: true, args: ['--no-sandbox'] });
for (const [html, pdf, nombre] of MANUALES) {
  const pag = await nav.newPage();
  await pag.goto(pathToFileURL(join(AQUI, html)).href, { waitUntil: 'networkidle0' });
  await pag.emulateMediaType('print');
  await pag.pdf({
    path: join(AQUI, pdf),
    format: 'letter',
    printBackground: true,
    preferCSSPageSize: true,
    displayHeaderFooter: true,
    headerTemplate: '<span></span>',
    footerTemplate: `<div style="width:100%;font-size:7.5pt;color:#6b6b75;padding:0 17mm;display:flex;justify-content:space-between;font-family:-apple-system,Segoe UI,Arial,sans-serif">
      <span>${nombre} · Control Maestro TvUAQ · FRACTAL</span><span>Página <span class="pageNumber"></span> de <span class="totalPages"></span></span></div>`,
  });
  console.log('PDF:', pdf);
  await pag.close();
}
await nav.close();
