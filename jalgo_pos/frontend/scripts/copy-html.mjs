// Copy the built index.html into Frappe's www folder so /jalgo-pos serves the SPA.
import fs from 'fs'
fs.copyFileSync('../jalgo_pos/public/frontend/index.html', '../jalgo_pos/www/jalgo-pos.html')
console.log('copied index.html -> jalgo_pos/www/jalgo-pos.html')
