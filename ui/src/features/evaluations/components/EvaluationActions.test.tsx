import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { EvaluationActionsButton, EvaluationActionForm } from './EvaluationActions'

const invalidateMutate = vi.fn()
const restoreMutate = vi.fn()
const overrideMutate = vi.fn()
const pinMutate = vi.fn()
const reEvaluateMutate = vi.fn()

vi.mock('../hooks', () => ({
  useInvalidateEvaluation: () => ({ mutate: invalidateMutate, isPending: false }),
  useRestoreEvaluation: () => ({ mutate: restoreMutate, isPending: false }),
  useOverrideStatus: () => ({ mutate: overrideMutate, isPending: false }),
  usePinBaseline: () => ({ mutate: pinMutate, isPending: false }),
  useReEvaluate: () => ({ mutate: reEvaluateMutate, isPending: false }),
}))

function renderWithQuery(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>)
}

describe('EvaluationActionsButton', () => {
  it('renders the Actions button for a non-invalidated evaluation', () => {
    renderWithQuery(
      <EvaluationActionsButton
        currentResult="pass"
        invalidated={false}
        activeAction={null}
        onSelectAction={vi.fn()}
      />,
    )
    expect(screen.getByText('Actions')).toBeInTheDocument()
  })

  it('shows action menu items when Actions button is clicked', () => {
    renderWithQuery(
      <EvaluationActionsButton
        currentResult="pass"
        invalidated={false}
        activeAction={null}
        onSelectAction={vi.fn()}
      />,
    )
    fireEvent.click(screen.getByText('Actions'))
    expect(screen.getByText('Invalidate')).toBeInTheDocument()
    expect(screen.getByText('Mark as Failure')).toBeInTheDocument()
    expect(screen.getByText('Pin Baseline')).toBeInTheDocument()
    expect(screen.getByText('Run Evaluations')).toBeInTheDocument()
  })

  it('shows "Mark as Successful" for a failed evaluation', () => {
    renderWithQuery(
      <EvaluationActionsButton
        currentResult="fail"
        invalidated={false}
        activeAction={null}
        onSelectAction={vi.fn()}
      />,
    )
    fireEvent.click(screen.getByText('Actions'))
    expect(screen.getByText('Mark as Successful')).toBeInTheDocument()
  })

  it('calls onSelectAction when a menu item is clicked', () => {
    const onSelectAction = vi.fn()
    renderWithQuery(
      <EvaluationActionsButton
        currentResult="pass"
        invalidated={false}
        activeAction={null}
        onSelectAction={onSelectAction}
      />,
    )
    fireEvent.click(screen.getByText('Actions'))
    fireEvent.click(screen.getByText('Invalidate'))
    expect(onSelectAction).toHaveBeenCalledWith('invalidate')
  })

  it('shows Restore action when evaluation is invalidated', () => {
    const onSelectAction = vi.fn()
    renderWithQuery(
      <EvaluationActionsButton
        currentResult="pass"
        invalidated={true}
        activeAction={null}
        onSelectAction={onSelectAction}
      />,
    )
    expect(screen.getByText('Actions')).toBeInTheDocument()
    fireEvent.click(screen.getByText('Actions'))
    expect(screen.getByText('Restore')).toBeInTheDocument()
    expect(screen.queryByText('Invalidate')).not.toBeInTheDocument()
    expect(screen.queryByText('Pin Baseline')).not.toBeInTheDocument()
    fireEvent.click(screen.getByText('Restore'))
    expect(onSelectAction).toHaveBeenCalledWith('restore')
  })

  it('shows Add Note item when onAddNote is provided', () => {
    const onAddNote = vi.fn()
    renderWithQuery(
      <EvaluationActionsButton
        currentResult="pass"
        invalidated={false}
        activeAction={null}
        onSelectAction={vi.fn()}
        onAddNote={onAddNote}
      />,
    )
    fireEvent.click(screen.getByText('Actions'))
    expect(screen.getByText('Add Note')).toBeInTheDocument()
    fireEvent.click(screen.getByText('Add Note'))
    expect(onAddNote).toHaveBeenCalled()
  })
})

describe('EvaluationActionForm', () => {
  it('renders invalidate form with reason and author fields', () => {
    renderWithQuery(
      <EvaluationActionForm
        evalId="e1"
        currentResult="pass"
        activeAction="invalidate"
        onClose={vi.fn()}
      />,
    )
    expect(screen.getByText('Invalidate')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Reason…')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Author')).toBeInTheDocument()
  })

  it('renders override form with reason and author fields', () => {
    renderWithQuery(
      <EvaluationActionForm
        evalId="e1"
        currentResult="pass"
        activeAction="override"
        onClose={vi.fn()}
      />,
    )
    expect(screen.getByText('Mark as Failure')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Reason…')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Author')).toBeInTheDocument()
  })

  it('renders baseline form with reason and author fields', () => {
    renderWithQuery(
      <EvaluationActionForm
        evalId="e1"
        currentResult="pass"
        activeAction="baseline"
        onClose={vi.fn()}
      />,
    )
    expect(screen.getByText('Pin Baseline')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Reason…')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Author')).toBeInTheDocument()
  })

  it('renders re-evaluate form with date input and baseline checkbox', () => {
    renderWithQuery(
      <EvaluationActionForm
        evalId="e1"
        currentResult="pass"
        activeAction="re-evaluate"
        onClose={vi.fn()}
        assetName="my-asset"
        sloName="my-slo"
      />,
    )
    expect(screen.getByText('Run Evaluations')).toBeInTheDocument()
    expect(screen.getByText('Run from last baseline')).toBeInTheDocument()
    expect(screen.getByText('Start date')).toBeInTheDocument()
  })

  it('calls onClose when Cancel button is clicked', () => {
    const onClose = vi.fn()
    renderWithQuery(
      <EvaluationActionForm
        evalId="e1"
        currentResult="pass"
        activeAction="invalidate"
        onClose={onClose}
      />,
    )
    fireEvent.click(screen.getByText('Cancel'))
    expect(onClose).toHaveBeenCalled()
  })

  it('disables Confirm when reason is empty', () => {
    renderWithQuery(
      <EvaluationActionForm
        evalId="e1"
        currentResult="pass"
        activeAction="invalidate"
        onClose={vi.fn()}
      />,
    )
    expect(screen.getByText('Confirm')).toBeDisabled()
  })

  it('enables Confirm when reason and author are provided', () => {
    renderWithQuery(
      <EvaluationActionForm
        evalId="e1"
        currentResult="pass"
        activeAction="invalidate"
        onClose={vi.fn()}
      />,
    )
    fireEvent.change(screen.getByPlaceholderText('Reason…'), { target: { value: 'bad data' } })
    fireEvent.change(screen.getByPlaceholderText('Author'), { target: { value: 'tester' } })
    expect(screen.getByText('Confirm')).toBeEnabled()
  })

  it('calls invalidate mutation on form submit', () => {
    invalidateMutate.mockClear()
    renderWithQuery(
      <EvaluationActionForm
        evalId="e1"
        currentResult="pass"
        activeAction="invalidate"
        onClose={vi.fn()}
      />,
    )
    fireEvent.change(screen.getByPlaceholderText('Reason…'), { target: { value: 'Bad data' } })
    fireEvent.change(screen.getByPlaceholderText('Author'), { target: { value: 'alice' } })
    fireEvent.click(screen.getByText('Confirm'))
    expect(invalidateMutate).toHaveBeenCalled()
  })

  it('calls override mutation on form submit', () => {
    overrideMutate.mockClear()
    renderWithQuery(
      <EvaluationActionForm
        evalId="e1"
        currentResult="pass"
        activeAction="override"
        onClose={vi.fn()}
      />,
    )
    fireEvent.change(screen.getByPlaceholderText('Reason…'), { target: { value: 'Override reason' } })
    fireEvent.change(screen.getByPlaceholderText('Author'), { target: { value: 'alice' } })
    fireEvent.click(screen.getByText('Confirm'))
    expect(overrideMutate).toHaveBeenCalled()
  })
})
