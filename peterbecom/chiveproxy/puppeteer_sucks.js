const puppeteer = require('puppeteer');

/* See other great tips on:
https://hackernoon.com/tips-and-tricks-for-web-scraping-with-puppeteer-ed391a63d952
*/

if (process.argv.length < 3) {
  console.warn('Missing URL argument');
  process.exit(1);
}
const url = process.argv[2];

(async (url) => {
  const browser = await puppeteer.launch({
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu'],
    // defaultViewport: {
    //   width: 1920,
    //   height: 2080,
    // },
  });
  const page = await browser.newPage();
  page.setDefaultTimeout(10 * 1000);
  let response;
  try {
    response = await page.goto(url, {
      timeout: 100 * 1000,
      waitUntil: 'load',
    });
  } catch (error) {
    console.warn(`Failed to goto ${url}`, error);
    await browser.close();
    process.exit(2);
  }
  let exit = 0;
  if (response && response.ok()) {
    // await page.screenshot({ path: '/tmp/screenshot.png' });
    let html = await page.content();
    process.stdout.write(html);
  } else if (!response) {
    console.warn(`Response was null for ${url}`);
    exit = 3;
  } else {
    console.warn(`Response was ${response.status()} for ${url}`);
    exit = 4;
  }
  await browser.close();

  // Don't process.exit() if there wasn't a problem. Node might still be busy
  // writing to stdout.
  if (exit) {
    process.exit(exit);
  }
})(url);
