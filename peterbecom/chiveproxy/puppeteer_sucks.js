const puppeteer = require('puppeteer');

if (process.argv.length < 3) {
  console.warn('Missing URL argument');
  process.exit(1);
}
const url = process.argv[2];

(async url => {
  const browser = await puppeteer.launch();
  const page = await browser.newPage();
  await page.goto(url);
  // await page.screenshot({ path: 'screenshot.png' });
  const html = await page.content();
  await browser.close();
  console.log(html);
})(url);
