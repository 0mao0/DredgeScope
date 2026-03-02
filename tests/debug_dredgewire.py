import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        url = "https://dredgewire.com/category/company-people/"
        print(f"Loading {url}...")
        await page.goto(url)
        await page.wait_for_timeout(5000)
        
        links = await page.evaluate("""() => {
            const anchors = Array.from(document.querySelectorAll('a'));
            return anchors.map(a => ({
                text: a.innerText.trim(),
                href: a.href,
                class: a.className,
                outerHTML: a.outerHTML.substring(0, 100)
            }));
        }""")
        
        print(f"Found {len(links)} links.")
        
        # Find specific article link and print its parents
        target_text = "DCA Submits Comments to BOEM"
        print(f"Searching for link containing '{target_text}'...")
        
        info = await page.evaluate("""(target) => {
            const anchors = Array.from(document.querySelectorAll('a'));
            const link = anchors.find(a => a.innerText.includes(target));
            if (!link) return "Link not found";
            
            const parents = [];
            let el = link.parentElement;
            while (el && el.tagName !== 'BODY') {
                parents.push(`${el.tagName}.${el.className}#${el.id}`);
                el = el.parentElement;
            }
            return parents.join(' > ');
        }""", target_text)
        
        print(f"Parents: {info}")
            
        await browser.close()
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
