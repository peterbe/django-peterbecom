import { WebView } from "bun"
import { parseArgs } from "util"

async function main() {
  const { values, positionals } = parseArgs({
    args: Bun.argv,
    options: {
      screenshot: {
        type: "string",
      },
      body: {
        type: "boolean",
      },
      head: {
        type: "boolean",
      },
      help: {
        type: "boolean",
      },
    },
    strict: true,
    allowPositionals: true,
  })

  // console.log(values)
  const args = positionals.slice(2)

  if (values.help || args.length === 0) {
    // console.log(positionals)
    const executable = (positionals[0] || "bun").split("/").slice(-1)[0]
    const program = (positionals[1] || "html-getter.ts").split("/").slice(-1)[0]
    console.log(`Usage: ${executable} ${program} [options] <url>`)
    console.log("Options:")
    console.log(
      "  --screenshot <path>  Save a screenshot of the page to the specified path",
    )
    console.log(
      "  --head               Output only the head HTML instead of the full document",
    )
    console.log(
      "  --body               Output only the body HTML instead of the full document",
    )
    console.log("  -h, --help           Show this help message")
    if (args.length === 0) {
      console.error("Error: URL is required")
      process.exit(1)
    }
    return
  }

  const url = args[0]
  if (args.length !== 1) {
    throw new Error("Exactly one positional argument is required")
  }
  if (!url) {
    throw new Error("URL is required")
  }
  if (url.startsWith("http://") || url.startsWith("https://")) {
    // valid
    if (!URL.canParse(url)) {
      throw new Error("Invalid URL")
    }
  } else {
    throw new Error("URL must start with http:// or https://")
  }

  // console.log(values)
  // console.log(args)

  await using view = new WebView({ width: 2000, height: 3000 })
  await view.navigate(url)
  if (values.head) {
    console.log(await view.evaluate("document.head.innerHTML"))
  } else if (values.body) {
    console.log(await view.evaluate("document.body.innerHTML"))
  } else {
    console.log(await view.evaluate("document.documentElement.outerHTML"))
  }

  if (values.screenshot) {
    const png = await view.screenshot()
    await Bun.write(values.screenshot, png)
    // stderr to avoid mixing with stdout which is used for HTML output
    console.error("Screenshot saved to", values.screenshot)
  }
}
main()
