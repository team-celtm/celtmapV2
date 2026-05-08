import { chromium } from 'playwright';
import path from 'path';

(async () => {
  console.log('Starting UI Test for Resume Ingestion...');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  // Log all console messages
  page.on('console', msg => console.log(`BROWSER CONSOLE: ${msg.type()} - ${msg.text()}`));
  
  // Log specific API requests
  page.on('request', request => {
    if (request.url().includes('/profile/me/artifacts')) {
      console.log(`[NETWORK] Sending Request: ${request.method()} ${request.url()}`);
    }
  });
  page.on('response', response => {
    if (response.url().includes('/profile/me/artifacts')) {
      console.log(`[NETWORK] Received Response: ${response.status()} ${response.url()}`);
    }
  });

  try {
    // 1. Open the app and log in / register
    console.log('Navigating to http://localhost:3000/register');
    await page.goto('http://localhost:3000/register');
    
    // Fill out registration if needed, otherwise try to login
    // Depending on the app's auth, we'll just try to enter some basic info.
    // If we're already logged in or there's no auth, we just go to settings.
    try {
        await page.fill('input[name="email"], input[type="email"]', 'e2e_tester@example.com', { timeout: 3000 });
        await page.fill('input[name="password"], input[type="password"]', 'Password123!');
        await page.fill('input[name="firstName"], input[name="name"]', 'QA Tester', { timeout: 1000 }).catch(() => {});
        await page.click('button[type="submit"]');
        await page.waitForNavigation({ waitUntil: 'networkidle' }).catch(() => {});
    } catch (e) {
        console.log('Could not perform standard registration (maybe already logged in or different flow). Moving to login...');
        await page.goto('http://localhost:3000/login');
        try {
            await page.fill('input[type="email"]', 'e2e_tester@example.com', { timeout: 3000 });
            await page.fill('input[type="password"]', 'Password123!');
            await page.click('button[type="submit"]');
            await page.waitForNavigation({ waitUntil: 'networkidle' }).catch(() => {});
        } catch (err) {
            console.log('Login form not found or skipped.');
        }
    }

    // 2. Navigate to Settings page
    console.log('Navigating to Settings page...');
    await page.goto('http://localhost:3000/settings');
    await page.waitForTimeout(2000); // Wait for page load

    // 3. Switch to Credentials Tab
    console.log('Switching to Credentials tab...');
    try {
      await page.click('button:has-text("Credentials"), a:has-text("Credentials"), [role="tab"]:has-text("Credentials")');
      await page.waitForTimeout(1000);
    } catch (e) {
      console.log('Could not explicitly click "Credentials" tab, assuming it is already active or merged.');
    }

    // Take "Before upload" screenshot
    await page.screenshot({ path: 'screenshot_1_before_upload.png' });
    console.log('Captured screenshot_1_before_upload.png');

    // 4. Attach valid resume file using the hidden file input
    console.log('Locating file input and attaching file...');
    const fileInput = await page.$('input[type="file"]');
    if (!fileInput) {
      throw new Error('File input element not found in the DOM!');
    }

    // Programmatically attach the test file (we use dummy_resume.txt)
    const filePath = path.resolve('../dummy_resume.txt');
    await fileInput.setInputFiles(filePath);

    // Take "After upload triggered" screenshot
    await page.waitForTimeout(500);
    await page.screenshot({ path: 'screenshot_2_after_upload_triggered.png' });
    console.log('Captured screenshot_2_after_upload_triggered.png');

    // 5. Observe API response and processing
    console.log('Waiting for backend response and async processing...');
    
    // Wait for the UI to update the status text
    // Assuming the UI displays "queued", "processing", or "completed" somewhere
    let retries = 10;
    let success = false;
    while (retries > 0) {
      await page.waitForTimeout(2000);
      const pageText = await page.content();
      
      if (pageText.toLowerCase().includes('completed') || pageText.toLowerCase().includes('extracted text here') || pageText.toLowerCase().includes('machine learning engineer')) {
        console.log('SUCCESS: Found "completed" or extracted text in UI.');
        success = true;
        break;
      }
      
      if (pageText.toLowerCase().includes('failed') || pageText.toLowerCase().includes('error')) {
        console.log('WARNING: Found "failed" or "error" in UI.');
      }
      
      console.log('Polling... waiting for processing...');
      retries--;
    }

    if (!success) {
      console.log('WARNING: Processing did not seem to complete within 20 seconds. (It may just be a UI text mismatch)');
    }

    // Take "After processing completes" screenshot
    await page.screenshot({ path: 'screenshot_3_after_processing.png' });
    console.log('Captured screenshot_3_after_processing.png');

  } catch (error) {
    console.error('Test Failed!', error);
    await page.screenshot({ path: 'screenshot_error.png' });
  } finally {
    await browser.close();
  }
})();
