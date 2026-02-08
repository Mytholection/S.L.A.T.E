# Spec 012: Schematic GUI Layout
<!-- Modified: 2026-02-08T00:00:00Z | Author: CLAUDE | Change: Create wiki page for Schematic GUI Layout -->

**Status**: Implementing
**Created**: 2026-02-08
**Depends On**: spec-007 (Design System), spec-008 (Guided Experience), spec-011 (Schematic SDK)

## Overview

This specification defines layout standards for integrating schematic diagrams as first-class visualization components within the SLATE dashboard. Schematics become part of SLATE's **Generative UI protocols** alongside the locked theme (v3.0.0).

## Layout Zones

| Zone | Purpose |
|------|---------|
| **Hero Zone** | Full-width schematic as primary visual anchor |
| **Widget Zone** | Compact schematics in sidebars/panels |
| **Detail Zone** | Focused component diagrams in modals/overlays |
| **Background Zone** | Subtle schematic patterns as visual texture |

## Widget Types

### 1. Hero Schematic Widget

Full-width primary visualization for the dashboard main area.

```css
.schematic-hero {
    width: 100%;
    max-width: 1200px;
    height: clamp(300px, 50vh, 500px);
    background: var(--blueprint-bg);
    border: 1px solid var(--blueprint-grid);
    border-radius: 16px;
}
```

### 2. Compact Widget

Sidebar/panel schematic for quick system overview.

```css
.schematic-compact {
    width: 100%;
    aspect-ratio: 16 / 10;
    background: var(--surface-dark);
    border: 1px solid var(--border-default);
    border-radius: 8px;
}
```

### 3. Card Schematic

Embedded within content cards for contextual visualization.

### 4. Modal Schematic

Full-detail overlay view for expanded exploration.

## Status Visualization

| Status | Background | Border | Indicator |
|--------|------------|--------|-----------|
| Active | `rgba(34, 197, 94, 0.1)` | `#22C55E` | Green pulse |
| Pending | `rgba(245, 158, 11, 0.1)` | `#F59E0B` | Amber pulse |
| Error | `rgba(239, 68, 68, 0.1)` | `#EF4444` | Red pulse |
| Inactive | `rgba(107, 114, 128, 0.1)` | `#6B7280` | No animation |

## WebSocket Integration

Live updates via WebSocket connection:

```javascript
const ws = new WebSocket('ws://127.0.0.1:8080/api/schematic/ws/live');

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === 'schematic_update') {
        document.querySelector('.schematic-content').innerHTML = data.svg;
    }
};
```

## Responsive Breakpoints

| Breakpoint | Width | Layout |
|------------|-------|--------|
| Desktop XL | >=1440px | Full grid, hero + side panel |
| Desktop | >=1200px | Full grid, hero + collapsible side |
| Tablet | >=768px | Stacked, hero above content |
| Mobile | <768px | Stacked, compact schematic |

## Implementation Priority

### Phase 1: Core Integration (Complete)
- [x] Schematic API module
- [x] Dashboard hero widget
- [x] WebSocket live updates

### Phase 2: Widget Library (In Progress)
- [ ] Compact sidebar widget
- [ ] Card schematic component
- [ ] Modal detail view
- [ ] Status overlay system

### Phase 3: Interactive Features (Planned)
- [ ] Component hover tooltips
- [ ] Click-to-focus zoom
- [ ] Connection highlighting
- [ ] Real-time activity flow animation

## Files

- `slate/schematic_api.py` - API router for schematic endpoints
- `slate_web/dashboard_schematics.py` - Dashboard integration
- `slate_web/dashboard_template.py` - Template with hero widget

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/schematic/system` | GET | System architecture schematic |
| `/api/schematic/live` | GET | Live system state schematic |
| `/api/schematic/ws/live` | WS | WebSocket live updates |

## Related Specifications

- [Spec 007: Design System](Spec-007-Design-System)
- [Spec 011: Schematic SDK](Spec-011-Schematic-SDK)
