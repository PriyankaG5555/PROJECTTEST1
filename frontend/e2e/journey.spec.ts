import { expect, test } from '@playwright/test'

// P0 journey: signup → create trip → add activity → finalize → export → reopen → delete account.
test('a traveller plans, finalizes and exports a trip', async ({ page }) => {
  const username = `e2e_${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
  const password = 'e2e-password-123'

  await page.goto('/signup')
  await page.getByLabel('Username').fill(username)
  await page.getByLabel('Password', { exact: true }).fill(password)
  await page.getByLabel('Confirm password').fill(password)
  await page.getByRole('button', { name: 'Create account' }).click()
  await expect(page.getByRole('heading', { name: 'My trips' })).toBeVisible()
  await expect(page.getByText('No trips yet')).toBeVisible()

  await page.getByRole('link', { name: '+ New trip' }).first().click()
  await page.getByLabel('Destination').fill('Goa')
  await page.getByLabel('Start date').fill('2026-11-14')
  await page.getByLabel('End date').fill('2026-11-17')
  await page.getByLabel('Trip type').selectOption('friends')
  await page.getByRole('button', { name: 'Create trip' }).click()
  await expect(page.getByRole('heading', { name: 'Goa' })).toBeVisible()
  await expect(page.getByRole('region', { name: /^Day \d$/ })).toHaveCount(4)

  const day1 = page.getByRole('region', { name: 'Day 1' })
  await day1.getByRole('button', { name: '+ Add activity' }).click()
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel('Destination name').fill('Baga Beach')
  await dialog.getByLabel('Start time').fill('09:30')
  await dialog.getByLabel('Cost in ₹').fill('1250')
  await dialog.getByLabel('High').check()
  await dialog.getByRole('button', { name: 'Add activity' }).click()
  await expect(day1.getByText('Baga Beach')).toBeVisible()
  await expect(day1.getByText('₹1,250').first()).toBeVisible()

  await expect(page.getByRole('link', { name: 'Export PDF' })).toHaveCount(0)
  await page.getByRole('button', { name: 'Finalize this draft' }).click()
  await page.getByRole('dialog').getByRole('button', { name: 'Finalize' }).click()
  await expect(page.getByText('Finalized', { exact: true })).toBeVisible()
  await expect(day1.getByRole('button', { name: '+ Add activity' })).toHaveCount(0)

  const download = page.waitForEvent('download')
  await page.getByRole('link', { name: 'Export PDF' }).click()
  expect((await download).suggestedFilename()).toBe('GhumakkadYatri-Goa-2026-11-14.pdf')

  await page.getByRole('button', { name: 'Reopen for editing' }).click()
  await page.getByRole('dialog').getByRole('button', { name: 'Reopen' }).click()
  await expect(day1.getByRole('button', { name: '+ Add activity' })).toBeVisible()

  await page.getByRole('link', { name: username }).click()
  await page.getByRole('button', { name: 'Delete my account' }).click()
  await page.getByRole('dialog').getByLabel('Password').fill(password)
  await page.getByRole('dialog').getByRole('button', { name: 'Delete account' }).click()
  await expect(page.getByText('Your account has been deleted.')).toBeVisible()
})

test('protected pages redirect to login', async ({ page }) => {
  await page.goto('/trips')
  await expect(page).toHaveURL(/\/login\?next=%2Ftrips/)
  await expect(page.getByRole('heading', { name: 'Welcome back' })).toBeVisible()
})
