import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { afterEach, describe, it, expect, vi } from 'vitest'
import { CategoryForm } from './CategoryForm'

describe('CategoryForm', () => {
  afterEach(() => cleanup())

  it('rejects invalid name', () => {
    const onSubmit = vi.fn()
    render(<CategoryForm onSubmit={onSubmit} onCancel={() => {}} />)
    fireEvent.change(screen.getByLabelText(/name/i), { target: { value: 'Bad Name' } })
    fireEvent.change(screen.getByLabelText(/label/i), { target: { value: 'OK' } })
    fireEvent.click(screen.getByRole('button', { name: /save/i }))
    expect(onSubmit).not.toHaveBeenCalled()
    expect(screen.getByText(/lowercase-hyphenated/i)).toBeInTheDocument()
  })

  it('rejects empty label', () => {
    const onSubmit = vi.fn()
    render(<CategoryForm onSubmit={onSubmit} onCancel={() => {}} />)
    fireEvent.change(screen.getByLabelText(/name/i), { target: { value: 'ok' } })
    fireEvent.change(screen.getByLabelText(/label/i), { target: { value: '' } })
    fireEvent.click(screen.getByRole('button', { name: /save/i }))
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('submits valid input', () => {
    const onSubmit = vi.fn()
    render(<CategoryForm onSubmit={onSubmit} onCancel={() => {}} />)
    fireEvent.change(screen.getByLabelText(/name/i), { target: { value: 'release' } })
    fireEvent.change(screen.getByLabelText(/label/i), { target: { value: 'Release' } })
    fireEvent.click(screen.getByRole('button', { name: /save/i }))
    expect(onSubmit).toHaveBeenCalledWith({
      name: 'release',
      label: 'Release',
      color: 'sky',
      showOnGraph: true,
    })
  })
})
