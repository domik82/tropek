import { test, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Button } from './button'

test('renders default variant', () => {
  render(<Button>Click me</Button>)
  expect(screen.getByRole('button', { name: 'Click me' })).toBeInTheDocument()
})

test('renders destructive variant', () => {
  render(<Button variant="destructive">Delete</Button>)
  expect(screen.getByRole('button', { name: 'Delete' })).toBeInTheDocument()
})

test('renders ghost variant', () => {
  render(<Button variant="ghost">Ghost</Button>)
  expect(screen.getByRole('button', { name: 'Ghost' })).toBeInTheDocument()
})

test('renders outline variant', () => {
  render(<Button variant="outline">Cancel</Button>)
  expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument()
})

test('renders xs size', () => {
  render(<Button size="xs">Tiny</Button>)
  expect(screen.getByRole('button', { name: 'Tiny' })).toBeInTheDocument()
})

test('renders sm size', () => {
  render(<Button size="sm">Small</Button>)
  expect(screen.getByRole('button', { name: 'Small' })).toBeInTheDocument()
})

test('renders disabled state', () => {
  render(<Button disabled>Disabled</Button>)
  expect(screen.getByRole('button', { name: 'Disabled' })).toBeDisabled()
})
