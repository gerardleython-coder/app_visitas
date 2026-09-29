---
name: Pastoral Serenity
colors:
  surface: '#f6fbf5'
  surface-dim: '#d7dbd6'
  surface-bright: '#f6fbf5'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f0f5f0'
  surface-container: '#ebefea'
  surface-container-high: '#e5e9e4'
  surface-container-highest: '#dfe4df'
  on-surface: '#181d1a'
  on-surface-variant: '#414844'
  inverse-surface: '#2c322e'
  inverse-on-surface: '#edf2ed'
  outline: '#717973'
  outline-variant: '#c1c8c2'
  surface-tint: '#3f6653'
  primary: '#012d1d'
  on-primary: '#ffffff'
  primary-container: '#1b4332'
  on-primary-container: '#86af99'
  inverse-primary: '#a5d0b9'
  secondary: '#2c694e'
  on-secondary: '#ffffff'
  secondary-container: '#aeeecb'
  on-secondary-container: '#316e52'
  tertiary: '#4e0f00'
  on-tertiary: '#ffffff'
  tertiary-container: '#741b00'
  on-tertiary-container: '#ff835f'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#c1ecd4'
  primary-fixed-dim: '#a5d0b9'
  on-primary-fixed: '#002114'
  on-primary-fixed-variant: '#274e3d'
  secondary-fixed: '#b1f0ce'
  secondary-fixed-dim: '#95d4b3'
  on-secondary-fixed: '#002114'
  on-secondary-fixed-variant: '#0e5138'
  tertiary-fixed: '#ffdbd1'
  tertiary-fixed-dim: '#ffb5a0'
  on-tertiary-fixed: '#3b0900'
  on-tertiary-fixed-variant: '#862201'
  background: '#f6fbf5'
  on-background: '#181d1a'
  surface-variant: '#dfe4df'
typography:
  headline-lg:
    fontFamily: Literata
    fontSize: 26px
    fontWeight: '600'
    lineHeight: 34px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Literata
    fontSize: 22px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Literata
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
  title-md:
    fontFamily: Manrope
    fontSize: 16px
    fontWeight: '700'
    lineHeight: 22px
    letterSpacing: -0.01em
  title-sm:
    fontFamily: Manrope
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
  body-lg:
    fontFamily: Manrope
    fontSize: 15px
    fontWeight: '400'
    lineHeight: 22px
  body-md:
    fontFamily: Manrope
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Manrope
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
  label-lg:
    fontFamily: Manrope
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 18px
  label-md:
    fontFamily: Manrope
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.02em
  label-sm:
    fontFamily: Manrope
    fontSize: 11px
    fontWeight: '700'
    lineHeight: 14px
    letterSpacing: 0.04em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  gutter: 1rem
  margin: 1rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.75rem
  space-lg: 1rem
  space-xl: 1.5rem
---

## Brand & Style

This design system is tailored for purposeful pastoral stewardship and community care. Its identity balances administrative diligence with warmth and spiritual dignity, speaking to district administrators, local pastors, and cell-group leaders navigating structured pastoral visits, church registries, and community follow-ups.

The aesthetic fuses modern editorial clarity with understated utility:
- **Tone:** Grounded, revered, orderly, and deeply human. Avoids both cold enterprise software sterility and flashy consumer-social excess.
- **Design Movement:** Modern Editorial Minimalism. It relies on clean, breathable surfaces, high typographic distinction between humanistic serifs and technical sans-serifs, and crisp, structured containers.
- **Key Tenet:** High functional density without visual clutter. Data entry must feel dignified; field notes and pastoral observations receive respectful, focused framing.

## Colors

The palette establishes an atmosphere of organic stability, reliability, and calm authority through deep evergreen tones, balanced by smoke-white backgrounds and focused warm accents.

- **Primary (`#1B4332`) & Secondary (`#2D6A4F`):** Deep Forest Green and Pine Green. Used for core application navigation, key interactive triggers, selected states, and structural branding. Represents spiritual grounding, growth, and trust.
- **Tertiary Accent (`#D95D39` / `#C85A32`):** Terracotta / Coral. Reserved strictly for critical destructive actions, urgent follow-up flags, and dynamic counter badges requiring immediate pastoral intervention.
- **Warm Gold (`#D4A373` / `#E9C46A`):** Used deliberately for pending visits, pastoral observations, reminders, and secondary status markers.
- **Neutral Surface Palette:**
  - Base canvas: `#F4F6F4` (soft tinted smoke) and `#F8F9FA` (pure smoke white).
  - Elevated cards & sheets: `#FFFFFF`.
  - Borders and dividers: `#E2E8F0` and `#D1D5DB`.
- **Text & Contrast:**
  - Primary text: Deep Charcoal (`#1F2421`).
  - Secondary text / metadata: Slate Charcoal (`#4B5563`).
  - Disabled / hints: Muted Gray (`#9CA3AF`).
- **Semantic Status Signals:**
  - *Programada:* Soft slate blue/gray (`#2D6A4F` tint or `#475569` on `#F1F5F9`).
  - *Completada:* Deep Forest Green (`#1B4332` on `#E8F0EB`).
  - *Cancelada:* Terracotta tint (`#C85A32` on `#FDF2EE`).

## Typography

The typographic strategy deliberately separates editorial contemplation from administrative action:

1. **Literata:** Applied exclusively to top-level app bar headings, main section intros, and formal screen titles (e.g., "Registro de Visitas", "Detalle de Hermano"). Its literary serifs instill reverence, calm, and permanence.
2. **Manrope:** Drives all transactional and structural UI elements — form labels, lists, metadata lines, dynamic cards, button text, badges, and bottom navigation. Its geometric humanist proportions ensure immediate legibility under bright sunlight or rapid handheld entry.
3. **Locale & Formatting:** All dates, times, and phone structures reflect Colombian standard syntax (`DD/MM/YYYY`, 12-hour format with `a.m.` / `p.m.` in Bogotá `America/Bogota` timezone).

## Layout & Spacing

Targeted for vertical handheld screens (390x844 pt base viewport):

- **Grid & Margins:** Fluid 4-column layout on mobile with `16px` (`1rem`) outer page margins and `16px` gutters.
- **Vertical Rhythm:** 4px baseline sub-grid. Common component spacing strictly relies on `4px` (`space-xs`), `8px` (`space-sm`), `12px` (`space-md`), `16px` (`space-lg`), and `24px` (`space-xl`).
- **Form Factor Discipline:** Content flows cleanly without nested cards inside cards. Top safe area pads app headers with minimum 12px; bottom navigation observes device home indicator heights with safe area insets.
- **Section Dividers:** 1px hairline rules (`#E2E8F0`) with 16px vertical margins or direct spatial grouping using `24px` spacers instead of heavy visual barriers.

## Elevation & Depth

Visual hierarchy is maintained via tonal separation and hairline boundaries rather than high-elevation drop shadows:

- **Surface Tiers:**
  - *Base Screen Floor:* `#F4F6F4` / `#F8F9FA`.
  - *Container / Card Surface:* Pure White (`#FFFFFF`).
  - *Modal Sheet / Dropdown Floor:* Pure White (`#FFFFFF`).
- **Outlines over Shadows:** Flat, crisp low-contrast strokes (`1px solid #E2E8F0`) frame every card, input, and panel.
- **Shadow Definition:** Shadows are sparse and ambient. When an element floats (e.g., bottom sheets, sticky action bars, or active search bars), it applies a diffused, low-opacity tint: `box-shadow: 0 4px 12px rgba(31, 36, 33, 0.05)`.
- No skeuomorphic bevels, no gradient fills, and no high-blur glassmorphic frost.

## Shapes

In strict accordance with the product principles, all primary UI elements employ a restrained corner radius of **8px or less**:

- **Cards, Sheets, Panels, and Dialogs:** `8px` (`rounded-lg` token cap at `0.5rem`).
- **Buttons and Inputs:** `6px` or `8px` (`0.375rem` - `0.5rem`).
- **Tags, Badges, and Status Chips:** `4px` or `6px` (`0.25rem` - `0.375rem`). Full pills are strictly reserved for tiny counter dots and circle avatar containers.
- **Dividers:** Crisp non-rounded 1px vector lines.

## Components

### 1. Primary & Secondary Buttons
- **Primary:** Background `#1B4332`, foreground `#FFFFFF`, border-radius `6px`, height `48px`, font `Manrope SemiBold 14px`. Tap state subtly shifts to `#2D6A4F`.
- **Secondary / Outlined:** Background transparent, border `1.5px solid #2D6A4F`, text `#2D6A4F`, height `48px`.
- **Destructive:** Background `#C85A32` or subtle red-tinted outline with `#C85A32` text.

### 2. Status Chips & Badges
- Compact height (`24px` - `28px`), border-radius `4px`, padding horizontal `8px`.
- **Programada:** Background `#EDF2F7`, text `#2D6A4F`, border `1px solid #CBD5E1`.
- **Completada:** Background `#E8F0EB`, text `#1B4332`, border `1px solid #C2DEC9`.
- **Cancelada:** Background `#FDF2EE`, text `#C85A32`, border `1px solid #F6D0C2`.

### 3. Lists & Cards
- **Single-tier Cards:** Background `#FFFFFF`, border `1px solid #E2E8F0`, border-radius `8px`, inner padding `12px` to `16px`. No multi-layered nesting; content sections use subtle dividers or label hierarchy.
- **List Tiles (Hermano / Visita item):** Minimalist 64px row with left avatar/initials box (`36x36px`, rounded `6px`, forest tint), primary label in `Manrope 14px Bold`, secondary detail line in `Manrope 12px Regular`, and right status badge.

### 4. Inputs & Form Fields
- Height `48px`, border-radius `6px`, background `#FFFFFF`, border `1px solid #D1D5DB`.
- Focused state: Border `1.5px solid #1B4332`, no heavy outer glow ring.
- Label: Positioned above the field in `Manrope SemiBold 12px`, `#1F2421`.
- Helper / Error: Positioned below in `11px`, error uses `#D95D39`.

### 5. Checkboxes & Radio Controls
- Checkbox: `18x18px`, border-radius `4px`, checked fill `#1B4332` with white checkmark.
- Radio: `18x18px` circle with `#1B4332` concentric dot when selected.

### 6. Role-Based Bottom Navigation Bar
- Background `#FFFFFF`, height `64px` + safe-area bottom padding, top border `1px solid #E2E8F0`.
- Iconography: Lucide-style line icons, 22px stroke weight 1.75px. Active item colored `#1B4332` with label in `Manrope 11px Bold`; inactive `#64748B`.
- **Dynamic Tabs by Role:**
  - **ADMIN:** Distritos, Iglesias, Usuarios, Reportes, Perfil.
  - **PASTOR:** Agenda, Hermanos, Visitas, Mi Iglesia, Perfil.
  - **LIDER:** Mis Visitas, Mi Grupo, Registro, Perfil.

### 7. Pastoral Observation Panel
- Callout card for sensitive field visit feedback: Light ivory/gold tint (`#FAF7F2`), left accent border `3px solid #D4A373`, border-radius `6px`, inner text `Manrope 13px Italic`.