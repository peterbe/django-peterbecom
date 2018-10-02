#!/usr/bin/env node
const yargs = require('yargs');

const puppeteer = require('puppeteer');

async function run(url, selector, imagepath, padding = 6, viewport) {
  const browser = await puppeteer.launch();
  const page = await browser.newPage();
  viewport = viewport || { width: 1000, height: 600, deviceScaleFactor: 1 };
  // Adjustments particular to this page to ensure we hit desktop breakpoint.
  //   page.setViewport(viewport);

  await page.goto(url, {
    waitUntil: 'networkidle2'
  });

  /**
   * Takes a screenshot of a DOM element on the page, with optional padding.
   *
   * @param {!{path:string, selector:string, padding:(number|undefined)}=} opts
   * @return {!Promise<!Buffer>}
   */
  async function screenshotDOMElement(opts = {}) {
    const padding = 'padding' in opts ? opts.padding : 0;
    const path = 'path' in opts ? opts.path : null;
    const selector = opts.selector;

    if (!selector) throw Error('Please provide a selector.');

    const rect = await page.evaluate(selector => {
      const element = document.querySelector(selector);
      if (!element) return null;
      const { x, y, width, height } = element.getBoundingClientRect();
      return { left: x, top: y, width, height };
    }, selector);

    if (!rect) {
      throw Error(`Could not find element that matches selector: ${selector}.`);
    }

    console.log(rect);

    return await page.screenshot({
      path,
      clip: {
        x: rect.left - padding,
        y: rect.top - padding,
        width: rect.width + padding * 2,
        height: rect.height + padding * 2
      }
    });
  }

  try {
    await screenshotDOMElement({
      path: imagepath,
      selector: selector,
      padding
    });
    browser.close();
  } catch (error) {
    browser.close();
    console.error(error);
    process.exit(1);
  }
}

var argv = yargs
  .usage(
    'Generate a screenshot PNG from a URL\n\nUsage: $0 url selector [options]'
  )
  .demandCommand(2)
  .help('help')
  .alias('help', 'h')
  .options({
    output: {
      alias: 'o',
      description: 'full path to save the image',
      requiresArg: false,
      required: true,
      default: 'screenshot.png'
    },
    padding: {
      description: 'pixels of padding around element',
      requiresArg: false,
      required: false,
      default: 6
    },
    'viewport-width': {
      alias: 'width',
      description: 'viewport width',
      requiresArg: false,
      required: false,
      default: 1000
    },
    'viewport-height': {
      alias: 'height',
      description: 'viewport height',
      requiresArg: false,
      required: false,
      default: 800
    },
    'viewport-device-scale-factor': {
      alias: 'scale',
      description: 'viewport deviceScaleFactor',
      requiresArg: false,
      required: false,
      default: 1
    }
  }).argv;

const [url, selector] = argv._;
// console.dir(argv);
// console.log(url);
// console.log(selector);
viewport = {
  width: argv.viewportWidth,
  height: argv.viewportHeight,
  deviceScaleFactor: argv.viewportDeviceScaleFactor
};

run(url, selector, argv.output, argv.padding, viewport);
