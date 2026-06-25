---
name: Titan Resilience
colors:
  surface: '#0b1326'
  surface-dim: '#0b1326'
  surface-bright: '#31394d'
  surface-container-lowest: '#060e20'
  surface-container-low: '#131b2e'
  surface-container: '#171f33'
  surface-container-high: '#222a3d'
  surface-container-highest: '#2d3449'
  on-surface: '#dae2fd'
  on-surface-variant: '#c1c7ce'
  inverse-surface: '#dae2fd'
  inverse-on-surface: '#283044'
  outline: '#8b9198'
  outline-variant: '#41474d'
  surface-tint: '#9eccf1'
  primary: '#9eccf1'
  on-primary: '#00344f'
  primary-container: '#003d5c'
  on-primary-container: '#7ba8cc'
  inverse-primary: '#346383'
  secondary: '#bdc2ff'
  on-secondary: '#242a66'
  secondary-container: '#3b417e'
  on-secondary-container: '#aab0f4'
  tertiary: '#fcaaff'
  on-tertiary: '#540f5d'
  tertiary-container: '#5e1b67'
  on-tertiary-container: '#d587d9'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#cae6ff'
  primary-fixed-dim: '#9eccf1'
  on-primary-fixed: '#001e30'
  on-primary-fixed-variant: '#184b6a'
  secondary-fixed: '#e0e0ff'
  secondary-fixed-dim: '#bdc2ff'
  on-secondary-fixed: '#0d1350'
  on-secondary-fixed-variant: '#3b417e'
  tertiary-fixed: '#ffd6fc'
  tertiary-fixed-dim: '#fcaaff'
  on-tertiary-fixed: '#36003e'
  on-tertiary-fixed-variant: '#6e2a75'
  background: '#0b1326'
  on-background: '#dae2fd'
  surface-variant: '#2d3449'
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
  label-md:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.05em
  mono-sm:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  unit: 4px
  container-margin: 24px
  gutter: 16px
  stack-sm: 8px
  stack-md: 16px
  stack-lg: 32px
---

## Brand & Style
The design system is engineered for high-stakes B2B SaaS environments, specifically targeting risk management, cybersecurity, and strategic infrastructure monitoring. The brand personality is authoritative, resilient, and deeply technical, evoking a sense of "command and control" through a sophisticated, high-fidelity aesthetic.

The visual style utilizes a **Corporate Modern** foundation infused with **Tonal Layering**. It prioritizes information density and clarity without sacrificing aesthetic depth. By moving away from standard traffic-light colors in favor of a bespoke, vibrant palette, the system reduces "alert fatigue" while maintaining clear hierarchical urgency. The interface should feel like a premium, precision tool—stable, responsive, and uncompromisingly professional.

## Colors
This design system employs a sophisticated dark-mode-first strategy using a deep navy/slate neutral base to ensure maximum contrast for the vibrant functional palette.

- **Primary & Interactive:** Deep Teal (#003d5c) serves as the main interactive surface, with Indigo (#464c89) utilized for secondary actions and hover states.
- **Risk Mapping:** 
    - **High Risk:** Replaced by Coral (#ff6b59) for critical alerts.
    - **Medium Risk:** Replaced by Amber (#ffa600) for warnings.
    - **Stable/Low Risk:** Represented by Purple (#954e9b) or Magenta (#dd4d88) to denote healthy but active system states.
- **Surface Strategy:** Backgrounds use a tiered neutral scale starting from #0f172a, moving to #1e293b for elevated containers to create structural depth.

## Typography
The system relies exclusively on **Inter** to maintain a systematic, utilitarian, and highly legible environment. For data-heavy views or system logs, **JetBrains Mono** is introduced as a secondary utility face.

Headlines are set with tight letter-spacing and heavy weights to project authority. Body text scales are optimized for density, utilizing a 14px base for complex dashboards to maximize "above-the-fold" data visibility. Uppercase labels are used sparingly for category headers and table column titles to provide clear structural scaffolding.

## Layout & Spacing
The layout follows a **Fluid Grid** model based on a 12-column system for desktop and a 4-column system for mobile. A 4px baseline grid governs all internal component spacing to ensure mathematical harmony.

- **Desktop:** 24px outer margins with 16px gutters.
- **Tablet:** 16px margins and gutters.
- **Mobile:** 12px margins. 

The vertical rhythm is tight, reflecting the B2B SaaS requirement for information density. Large "hero" whitespace is avoided in favor of "functional" whitespace that separates distinct data modules and logical groupings.

## Elevation & Depth
Depth is communicated through **Tonal Layers** rather than heavy shadows. In a dark environment, this system uses "inner glows" and subtle border treatments to simulate light catching the edges of elevated panels.

- **Level 0 (Base):** #0f172a (Deepest)
- **Level 1 (Cards/Sidebar):** #1e293b with a 1px border of #334155.
- **Level 2 (Modals/Popovers):** #1e293b with a subtle 10% opacity white outer stroke and a soft 16px ambient shadow to separate it from the main UI.

Interactive elements (buttons) use a slight 1px top-highlight to create a tactile, "pressed" or "raised" appearance consistent with high-fidelity professional tools.

## Shapes
The shape language is disciplined and geometric, utilizing "Soft" (rounded-sm/md) corners. 

- **Small Components:** Checkboxes, tags, and small buttons use a 4px (0.25rem) radius.
- **Standard Components:** Cards, input fields, and primary buttons use an 8px (0.5rem) radius.
- **Large Components:** Modals and main dashboard containers use a 12px (0.75rem) radius.

This subtle rounding prevents the UI from feeling aggressive (sharp) while maintaining a structured, architectural feel that distinguishes it from consumer-facing "bubbly" interfaces.

## Components
- **Buttons:** Primary buttons use a solid #003d5c (Deep Teal) with white text. Secondary buttons use an Indigo (#464c89) ghost style with a 1px border.
- **Status Chips:** High-risk indicators use a #ff6b59 background with 15% opacity and solid #ff6b59 text. Medium and Low risk follow the same formula using Amber and Purple respectively.
- **Input Fields:** Dark surfaces (#0f172a) with a #334155 border. On focus, the border transitions to Deep Teal with a subtle outer glow.
- **Data Tables:** Row heights are compact (40px-48px). Headers use the `label-md` typography style with a subtle bottom divider.
- **Cards:** Defined by a 1px #334155 border and a slightly lighter background than the canvas to create a containerized hierarchy for data modules.
- **Progress Bars:** Use Magenta (#dd4d88) for neutral progress and Coral/Amber for risk-based thresholds.