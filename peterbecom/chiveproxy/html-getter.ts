// import { WebView } from "bun"
// import { parseArgs } from "util"

// async function main() {
//   const { values, positionals } = parseArgs({
//     args: Bun.argv,
//     options: {
//       screenshot: {
//         type: "string",
//       },
//       body: {
//         type: "boolean",
//       },
//       head: {
//         type: "boolean",
//       },
//       help: {
//         type: "boolean",
//       },
//     },
//     strict: true,
//     allowPositionals: true,
//   })

//   // console.log(values)
//   const args = positionals.slice(2)

//   if (values.help || args.length === 0) {
//     // console.log(positionals)
//     const executable = (positionals[0] || "bun").split("/").slice(-1)[0]
//     const program = (positionals[1] || "html-getter.ts").split("/").slice(-1)[0]
//     console.log(`Usage: ${executable} ${program} [options] <url>`)
//     console.log("Options:")
//     console.log(
//       "  --screenshot <path>  Save a screenshot of the page to the specified path",
//     )
//     console.log(
//       "  --head               Output only the head HTML instead of the full document",
//     )
//     console.log(
//       "  --body               Output only the body HTML instead of the full document",
//     )
//     console.log("  -h, --help           Show this help message")
//     if (args.length === 0) {
//       console.error("Error: URL is required")
//       process.exit(1)
//     }
//     return
//   }

//   const url = args[0]
//   if (args.length !== 1) {
//     throw new Error("Exactly one positional argument is required")
//   }
//   if (!url) {
//     throw new Error("URL is required")
//   }
//   if (url.startsWith("http://") || url.startsWith("https://")) {
//     // valid
//     if (!URL.canParse(url)) {
//       throw new Error("Invalid URL")
//     }
//   } else {
//     throw new Error("URL must start with http:// or https://")
//   }

//   // console.log(values)
//   // console.log(args)

//   await using view = new WebView({ width: 2000, height: 3000 })
//   await view.navigate(url)
//   if (values.head) {
//     console.log(await view.evaluate("document.head.innerHTML"))
//   } else if (values.body) {
//     console.log(await view.evaluate("document.body.innerHTML"))
//   } else {
//     console.log(await view.evaluate("document.documentElement.outerHTML"))
//   }

//   if (values.screenshot) {
//     const png = await view.screenshot()
//     await Bun.write(values.screenshot, png)
//     // stderr to avoid mixing with stdout which is used for HTML output
//     console.error("Screenshot saved to", values.screenshot)
//   }
// }
// main()

import puppeteer from 'puppeteer';

/* See other great tips on:
https://hackernoon.com/tips-and-tricks-for-web-scraping-with-puppeteer-ed391a63d952
*/

const args = process.argv.slice(2);
if (args.includes('--help') || args.includes('-h')) {
  console.log('Usage: html_getter [options] <url>');
  console.log('Options:');
  process.exit(0);
}

if (args.length < 1) {
  throw new Error('URL argument is required');
}
const url = args[0];

(async (url) => {
  if (!url) throw new Error('URL is required');

  const browser = await puppeteer.launch({
    // headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu'],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1080, height: 1024 });
  page.setDefaultTimeout(10 * 1000);
  try {
    const response = await page.goto(url, {
      timeout: 100 * 1000,
      waitUntil: 'load',
    });

    // let exit = 0;
    if (response?.ok()) {
      const html = await page.content();
      process.stdout.write(html);
    } else if (!response) {
      throw new Error(`Response was null for ${url}`);
    } else {
      throw new Error(`Response was ${response.status()} for ${url}`);
    }
  } finally {
    await browser.close();
  }
})(url);
