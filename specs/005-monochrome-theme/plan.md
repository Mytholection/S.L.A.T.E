# Implementation Plan: Monochrome Theme

## Phase 1: Color Palette Update

Update CSS variables in `agents/slate_dashboard_server.py` (lines 403-416):

1. Replace `--bg-dark` with #0a0a0a
2. Replace `--bg-card` with rgba(18, 18, 18, 0.80)
3. Replace text colors with white/gray hierarchy
4. Keep only `--status-success` and `--status-error` for color
5. Add new `--status-pending` and `--status-active` (grays)
6. Add agent brightness variables

## Phase 2: Background Update

Update body styles (lines 420-429):
- Replace colored radial gradients with subtle white gradients
- Maintain glassmorphism effect

## Phase 3: Component Updates

Update individual components:
- Logo icon: white-to-gray gradient
- GPU icon: monochrome gradient
- Buttons: white/gray instead of blue
- Badges: monochrome with red/green only for status
- Task borders: gray for pending, white for active

## Phase 4: Agentic Flow Section

Add new dashboard section:
1. New CSS classes for flow visualization
2. HTML section with pipeline and agent grid
3. JavaScript functions for real-time updates
4. New `/api/agentic-flow` endpoint

## Dependencies

- No external dependencies
- Uses existing task and workflow APIs
