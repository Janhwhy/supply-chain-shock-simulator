---
name: Titan Resilience
colors:
  surface: '#101418'
  surface-dim: '#101418'
  surface-bright: '#36393e'
  surface-container-lowest: '#0b0f13'
  surface-container-low: '#181c20'
  surface-container: '#1c2024'
  surface-container-high: '#272a2f'
  surface-container-highest: '#31353a'
  on-surface: '#e0e2e9'
  on-surface-variant: '#c0c7d2'
  inverse-surface: '#e0e2e9'
  inverse-on-surface: '#2d3136'
  outline: '#8a919c'
  outline-variant: '#404751'
  surface-tint: '#99cbff'
  primary: '#99cbff'
  on-primary: '#003355'
  primary-container: '#4299e1'
  on-primary-container: '#002f4e'
  inverse-primary: '#00629d'
  secondary: '#ffb3ad'
  on-secondary: '#68000a'
  secondary-container: '#a00015'
  on-secondary-container: '#ffa9a2'
  tertiary: '#ffb68f'
  on-tertiary: '#542100'
  tertiary-container: '#e77328'
  on-tertiary-container: '#4e1e00'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#cfe5ff'
  primary-fixed-dim: '#99cbff'
  on-primary-fixed: '#001d34'
  on-primary-fixed-variant: '#004a78'
  secondary-fixed: '#ffdad7'
  secondary-fixed-dim: '#ffb3ad'
  on-secondary-fixed: '#410004'
  on-secondary-fixed-variant: '#930013'
  tertiary-fixed: '#ffdbca'
  tertiary-fixed-dim: '#ffb68f'
  on-tertiary-fixed: '#331100'
  on-tertiary-fixed-variant: '#773200'
  background: '#101418'
  on-background: '#e0e2e9'
  surface-variant: '#31353a'
typography:
  display-lg:
    fontFamily: Inter
    fontSize: 48px
    fontWeight: '700'
    lineHeight: 56px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.01em
  headline-lg-mobile:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  title-md:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-sm:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-caps:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '700'
    lineHeight: 16px
    letterSpacing: 0.05em
  data-mono:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 18px
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  base: 4px
  xs: 8px
  sm: 16px
  md: 24px
  lg: 40px
  xl: 64px
  gutter: 24px
  margin-safe: 32px
---

## Brand & Style

The design system is engineered for executive-level supply chain intelligence, where clarity under pressure is the primary objective. The brand personality is authoritative, vigilant, and analytical. It targets C-suite executives and risk managers who require high-density information without cognitive overload.

The visual style is **Corporate Modern with a "Glass-Data" influence**. It utilizes a deep, nocturnal foundation to make data visualizations oscillate and command attention. The aesthetic prioritizes "Precision Minimalism"—removing all non-essential decorative elements to focus on status indicators and risk vectors. The emotional response should be one of absolute control and predictive confidence.

## Colors

The palette is anchored in a deep navy-charcoal spectrum to provide a high-contrast stage for semantic signaling. 

- **Foundational Neutrals:** The background and surface colors are tiered to create a sense of depth without relying on heavy shadows. 
- **Semantic Risk Spectrum:** Red, Orange, and Green are reserved strictly for risk status (High, Medium, Low). These should never be used for decorative purposes or standard interactive states.
- **Action & Interactivity:** Electric Blue is the primary vehicle for interactivity, focus states, and highlighting specific data nodes within a complex set.
- **Data Visualization:** Use a curated set of desaturated variants of the primary blue for non-risk data (e.g., historical trends) to ensure they do not compete with critical risk alerts.

## Typography

This design system uses **Inter** for all UI and structural elements due to its exceptional legibility in high-density data environments. 

- **Data Presentation:** **JetBrains Mono** is introduced for specific data values, timestamps, and coordinates within graphs. This monospaced font ensures that numerical values align vertically in tables and charts, facilitating rapid scanning of figures.
- **Hierarchy:** Use `label-caps` for section headers and table column titles to create clear separation from row data.
- **Contrast:** Maintain a hierarchy where headlines are pure white (`#FFFFFF`) and body text is a secondary grey (`#94A3B8`) to reduce visual fatigue during long analytical sessions.

## Layout & Spacing

The layout utilizes a **12-column fluid grid** for the main dashboard content. 

- **Information Density:** While the platform is data-forward, it avoids clutter by using a strict 8px-based spacing system. 
- **The Dashboard Grid:** Dashboards use "Modular Tiles." Each tile is a card component that can span 3, 4, 6, or 12 columns.
- **Responsive Behavior:** 
  - **Desktop (1440px+):** 12 columns, 24px gutters, 40px outer margins.
  - **Tablet (768px - 1439px):** 8 columns, 16px gutters, 24px outer margins.
  - **Mobile (<767px):** 4 columns, 16px gutters, 16px outer margins. Cards typically stack into a single column.

## Elevation & Depth

This design system avoids traditional shadows in favor of **Tonal Layering and Border Definition**.

- **Level 0 (Background):** `#0F1724`. The foundation.
- **Level 1 (Cards/Panels):** `#1A2535`. Used for primary content containers.
- **Level 2 (Modals/Popovers):** `#243146`. Slightly lighter than the card background to simulate height.
- **The "Glass" Effect:** For interactive overlays (like tooltips over charts), use a background blur of 12px with a 60% opacity fill of the Surface color.
- **Borders:** All containers must have a 1px solid border of `#2A3F5F`. This "blueprint" aesthetic reinforces the technical, analytical nature of the platform. No drop shadows should be applied to standard cards.

## Shapes

The shape language is **Soft (0.25rem)**, providing a slight professional polish while maintaining a rigid, engineered feel. 

- **Primary Radius:** 4px for buttons, input fields, and small UI elements.
- **Container Radius:** 8px (`rounded-lg`) for main KPI cards and data tables.
- **Special Case:** Circular elements (gauges, status dots, and profile avatars) are permitted to maintain a 50% radius (pill/circle) to distinguish them from structural layout components.

## Components

- **KPI Cards:** Feature a `title-md` label, a `display-lg` primary metric, and a `data-mono` trend indicator (green for up/good, red for down/bad, unless the metric is risk-based, then inverted).
- **Data Tables:** Row hover states should use a subtle background shift to `#243146`. Use 1px borders between rows. Column headers use `label-caps`. 
- **Risk Badges:** High-contrast pills using the semantic risk colors. Use an "Outer Glow" effect (2px spread, 20% opacity of the color) for "High Risk" items only to create a subtle pulse of urgency.
- **Input Fields:** Dark fill (`#0F1724`), 1px border (`#2A3F5F`). On focus, the border transitions to Electric Blue.
- **Buttons:**
  - **Primary:** Electric Blue background with white text.
  - **Secondary:** Transparent background with a 1px Electric Blue border.
  - **Risk-Action:** Ghost button with Red text for destructive or high-risk mitigation actions.
- **Data Visualizations:** 
  - **Scatter Plots:** Use Electric Blue for nodes, with Red/Orange/Green highlights only for outliers exceeding risk thresholds.
  - **Heatmaps:** Use a monochromatic scale of the primary blue for density, or a diverging Red-Green scale for risk assessment.