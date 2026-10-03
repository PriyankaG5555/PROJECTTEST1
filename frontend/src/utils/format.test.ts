import { expect, test } from 'vitest'
import { dayCount, inr, longDate, shortDate } from './format'

test('inr uses Indian grouping and the rupee sign', () => {
  expect(inr(123456)).toBe('₹1,23,456')
  expect(inr(1250.5)).toBe('₹1,250.5')
  expect(inr(null)).toBe('₹0')
})

test('dates are formatted without timezone shifts', () => {
  expect(longDate('2026-11-14')).toBe('Sat, 14 Nov 2026')
  expect(shortDate('2026-11-14')).toBe('14 Nov')
})

test('dayCount includes both ends', () => {
  expect(dayCount('2026-11-14', '2026-11-17')).toBe(4)
  expect(dayCount('2026-11-14', '2026-11-14')).toBe(1)
})
