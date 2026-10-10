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

test('endTime and durationLabel', async () => {
  const { endTime, durationLabel } = await import('./format')
  expect(endTime('10:00', 90)).toBe('11:30')
  expect(endTime('23:00', 60)).toBe('24:00')
  expect(durationLabel(90)).toBe('1 h 30 min')
  expect(durationLabel(45)).toBe('45 min')
  expect(durationLabel(120)).toBe('2 h')
})
