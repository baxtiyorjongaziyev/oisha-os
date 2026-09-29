import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
            contexts = browser.contexts
            print(f"Connected! Context count: {len(contexts)}")
            for i, ctx in enumerate(contexts):
                print(f"Context {i}: {len(ctx.pages)} pages")
                for j, page in enumerate(ctx.pages):
                    print(f"  Page {j}: title='{page.title}' url='{page.url}'")
            await browser.close()
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
