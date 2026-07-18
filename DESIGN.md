# DESIGN.md — Dark Survival Game Wiki

## 1. Design Goal

Create a standalone game-wiki interface inspired by dark survival games, handmade field journals, gothic storybooks, weathered wood, parchment, charcoal, and ink illustration.

The interface should feel:

- dark
- handcrafted
- old
- slightly unsettling
- functional like a game encyclopedia
- dense but still readable
- atmospheric without hiding information

Do not reproduce copyrighted logos, characters, icons, illustrations, textures, or exact UI assets from existing games. Build original assets with a similar dark survival-fantasy direction.

---

## 2. Core Visual Language

### Visual keywords

- survival wiki
- dark fantasy
- hand-drawn
- scratched ink
- weathered wood
- aged parchment
- crooked frames
- gothic field journal
- dim campfire atmosphere
- game encyclopedia
- handmade interface
- rough ornamental borders

### Avoid

- glassmorphism
- neon colors
- modern SaaS styling
- excessive rounded corners
- glossy gradients
- perfect geometric frames
- large empty white spaces
- futuristic typography
- smooth corporate illustrations

---

## 3. Page Structure

Use a desktop-first three-column wiki layout.

```text
┌─────────────────────────────────────────────────────────────┐
│ Logo / masthead                              Search bar      │
├───────────────┬───────────────────────────────┬───────────────┤
│ Left sidebar  │ Main article/content area     │ Right widgets │
│ navigation    │                               │ and modules   │
└───────────────┴───────────────────────────────┴───────────────┘
```

### Desktop layout

- page max width: `1760px`
- outer page padding: `20px`
- left sidebar width: `170px`
- right sidebar width: `370px`
- column gap: `20px`
- main content: flexible
- header height: `140px` to `180px`
- content begins below the masthead

### Tablet layout

- hide or collapse the right sidebar below `1180px`
- left sidebar becomes a drawer below `960px`
- main content fills available width

### Mobile layout

- single-column layout
- sticky top navigation
- collapsible page sections
- cards and tables become horizontally scrollable where required
- decorative textures must not reduce text contrast

---

## 4. Color System

### Background colors

```css
--page-bg: #0d0b09;
--page-bg-elevated: #14110e;
--panel-bg: #1b1612;
--panel-bg-soft: #251d17;
--panel-bg-hover: #30251c;
```

### Parchment and wood

```css
--parchment-light: #c8ad82;
--parchment: #aa8963;
--parchment-dark: #806248;
--wood-light: #76563d;
--wood: #4b3427;
--wood-dark: #241913;
```

### Text

```css
--text-primary: #eee8dc;
--text-secondary: #c8bbab;
--text-muted: #8f8171;
--text-dark: #1b140f;
--text-link: #b89a3f;
--text-link-hover: #dbc477;
```

### Accents

```css
--accent-gold: #a98b35;
--accent-rust: #87462e;
--accent-blood: #712821;
--accent-moss: #596044;
--accent-bone: #d8ceb6;
--border-dark: #17100c;
--border-mid: #4e392a;
--border-light: #806246;
```

### Semantic colors

```css
--success: #65784d;
--warning: #a47b32;
--danger: #87362d;
--info: #536b75;
```

---

## 5. Typography

Use two complementary font categories.

### Display font

For:

- logo
- navigation panel titles
- major article headings
- card titles
- decorative labels

Characteristics:

- narrow
- irregular
- distressed
- gothic or hand-rendered
- high vertical rhythm
- visibly imperfect edges

Recommended open-source directions:

- `UnifrakturCook`
- `Pirata One`
- `Grenze Gotisch`
- `New Rocker`
- another original distressed display font

Do not use the display font for long paragraphs.

### Body font

For:

- article text
- metadata
- lists
- table contents
- descriptions

Recommended direction:

- readable serif
- slightly old-fashioned
- strong contrast on dark backgrounds

Possible choices:

- `Libre Baskerville`
- `Lora`
- `Cormorant Garamond`
- `Noto Serif`

### UI labels

Use a readable sans-serif only for small functional controls:

- search field
- tabs
- buttons
- table controls
- tooltips

Possible choices:

- `Inter`
- `Noto Sans`
- `Source Sans 3`

### Type scale

```css
--font-xs: 12px;
--font-sm: 14px;
--font-md: 16px;
--font-lg: 20px;
--font-xl: 28px;
--font-2xl: 38px;
--font-3xl: 56px;
```

### Line height

- body: `1.6`
- compact UI: `1.25`
- headings: `1.05` to `1.2`

---

## 6. Background Treatment

The page background should be nearly black with subtle illustrated silhouettes.

Use:

- original ink-style tree silhouettes
- faint circular line art
- scratched charcoal texture
- foggy dark brown overlays
- extremely low-opacity decorative motifs

Suggested layering:

```css
background:
  linear-gradient(rgba(10, 8, 6, 0.88), rgba(10, 8, 6, 0.96)),
  url("/assets/original-survival-background.webp"),
  #0d0b09;
background-size: cover;
background-attachment: fixed;
```

Rules:

- background artwork opacity should remain below `20%`
- main reading areas must have opaque dark surfaces
- decorative artwork must never compete with text

---

## 7. Header and Masthead

### Header layout

- large original wordmark on the left
- elongated search box on the right
- wide atmospheric background
- no conventional modern navbar across the full width

### Logo direction

Create an original title mark with:

- tall scratched lettering
- uneven strokes
- white or bone ink
- slight tilt and inconsistent baseline
- no reproduction of existing game logos

### Search field

Appearance:

- long and narrow
- dark wooden interior
- parchment or scratched-metal frame
- small search icon
- old label-like placeholder text
- width: `420px`
- height: `38px`

States:

- hover: border becomes slightly brighter
- focus: faint gold outline and inner glow
- no bright blue browser-default outline

---

## 8. Main Content Frame

The main content should look like a large dark panel mounted inside a rough wooden frame.

### Frame construction

Use nested layers:

1. irregular outer frame
2. thin highlight line
3. dark inner surface
4. optional corner ornaments
5. subtle inner shadow

```css
.content-shell {
  background: rgba(23, 18, 14, 0.96);
  border: 2px solid var(--border-dark);
  box-shadow:
    0 0 0 3px var(--border-mid),
    inset 0 0 30px rgba(0, 0, 0, 0.45);
}
```

For true irregular edges, prefer:

- SVG border images
- mask images
- pseudo-elements with slightly offset transforms
- original hand-drawn frame assets

Avoid uniform `border-radius`.

---

## 9. Left Navigation Panels

Create stacked navigation modules.

Each module contains:

- decorative title bar
- vertically stacked links
- optional collapse indicator
- rough corner details
- compact spacing

### Panel title

- display font
- font size: `24px`
- parchment-white text
- left aligned
- small gold collapse marker on the right

### Navigation link

```css
.sidebar-link {
  color: var(--text-link);
  font-size: 14px;
  line-height: 1.7;
  text-decoration: none;
}
```

Hover behavior:

- text shifts toward pale gold
- slight left-to-right ink underline
- background remains subtle
- no pill-shaped hover state

### Panel dimensions

- width: `100%`
- padding: `14px 16px`
- vertical gap between modules: `16px`

---

## 10. Top Content Tabs

Use compact rectangular tabs for actions such as:

- Main page
- Discussion
- Read
- View source
- History
- More

Style:

- dark brown fill
- parchment border
- distressed frame
- white or bone text
- height: `34px`
- padding: `0 14px`
- almost no corner rounding

Active tab:

- brighter parchment frame
- warmer brown surface
- slightly raised

Inactive tab:

- gray-brown surface
- lower contrast border

Hover:

- small upward movement: `translateY(-1px)`
- border brightens
- transition: `120ms`

---

## 11. Welcome Panel

Create a horizontal introduction block near the top of the main content.

Structure:

```text
[ornament]     Welcome to the Game Wiki     [ornament]
               short description
               secondary sentence
```

Style:

- center aligned
- thin brown border
- dark translucent background
- decorative original survival objects on both sides
- heading uses body sans or serif rather than the highly decorative display font
- italic emphasis allowed for the game title

Recommended padding:

- `24px 32px`

---

## 12. Hero Feature Card

Use a large feature image inside the main column.

### Image area

- aspect ratio near `16:9`
- original promotional-style illustration
- no copied game artwork
- dark gradient overlay at bottom
- previous and next controls centered vertically
- controls appear as parchment circles

### Caption overlay

At the bottom:

- large display headline
- one- or two-line description
- small “Read more” link aligned right
- black-to-transparent gradient behind text

```css
.hero-overlay {
  background: linear-gradient(
    to top,
    rgba(0, 0, 0, 0.92),
    rgba(0, 0, 0, 0.15)
  );
}
```

---

## 13. Right Sidebar Modules

Right-side modules can include:

- latest video
- crafting categories
- survival statistics
- featured guide
- recent updates
- community links
- seasonal content

### Module header

- parchment or muted clay background
- dark text
- small original icon
- bold label
- height around `34px`
- thin dark frame

### Module body

- dark inner panel
- thin brown border
- padding: `14px`
- content-dense
- no excessive whitespace

---

## 14. Crafting Grid

Display icon categories in a compact grid.

### Structure

- header row with tabs or filters
- category icons in 6 columns on desktop
- 5 columns on narrower screens
- 4 columns on mobile

### Icon style

All icons should be original and share:

- thick black outline
- muted colors
- rough painted fills
- slight asymmetry
- strong silhouette
- subtle parchment glow on hover

### Interaction

Hover:

- icon scales to `1.06`
- small wobble: `rotate(-1deg)`
- tooltip appears above
- selected item receives a muted gold underline

---

## 15. Cards

### Standard article card

- dark brown background
- thin weathered border
- optional parchment heading strip
- 16–20px internal padding
- minimal rounding: `0–3px`

### Item card

Contains:

- icon
- item name
- short description
- tags or stats
- link to article

### Featured card

- larger image
- prominent title
- stronger border
- gradient overlay

---

## 16. Infobox

The infobox is a major wiki component.

### Structure

```text
┌─────────────────────────┐
│ Item or Character Name  │
├─────────────────────────┤
│       Main image        │
├─────────────────────────┤
│ Health          100     │
│ Hunger          150     │
│ Sanity          200     │
├─────────────────────────┤
│ Description             │
└─────────────────────────┘
```

### Styling

- width: `300px` to `360px`
- floats right on article pages
- dark body
- parchment title row
- clear key-value sections
- original ink-style icons
- alternating row backgrounds
- rough exterior frame

---

## 17. Tables

Tables should resemble field-journal reference charts.

### Table header

- muted parchment background
- dark text
- bold
- thin dark separators

### Body rows

- alternating dark brown shades
- parchment-gray text
- compact but readable
- row hover adds a subtle warmer tone

### Responsive behavior

On mobile:

- horizontal scrolling
- sticky first column where helpful
- preserve readable minimum cell widths

---

## 18. Links

Default:

```css
a {
  color: var(--text-link);
}
```

Hover:

```css
a:hover {
  color: var(--text-link-hover);
  text-decoration-color: currentColor;
}
```

Visited links may use a muted copper tone.

Do not use bright default blue links.

---

## 19. Buttons

Buttons should look like attached labels, carved tabs, or parchment controls.

### Primary button

- parchment-brown fill
- dark text
- rough border
- compact rectangular shape

### Secondary button

- dark wood fill
- bone text
- gray-brown border

### Danger button

- deep blood-red fill
- pale text
- dark outline

### Button motion

```css
button:hover {
  transform: translateY(-1px) rotate(-0.3deg);
}

button:active {
  transform: translateY(1px);
}
```

Animation duration:

- `100ms` to `160ms`

---

## 20. Inputs and Forms

Inputs should look embedded into wooden or parchment frames.

### Text input

- dark inset background
- pale text
- muted placeholder
- rectangular form
- thin parchment border
- visible focus state in muted gold

### Checkbox and radio

Use custom original icons:

- scratched square
- hand-drawn circle
- ink-mark selected state

Always preserve keyboard accessibility.

---

## 21. Borders and Decorative Frames

The design depends heavily on rough frames.

Preferred implementation order:

1. original SVG frame assets
2. `border-image`
3. mask-image
4. pseudo-element layering
5. plain CSS border as fallback

Create several reusable frame variants:

- `frame-small`
- `frame-panel`
- `frame-content`
- `frame-header`
- `frame-tooltip`

Do not use the same border for every component.

---

## 22. Texture Rules

Textures should be subtle and reusable.

Recommended texture categories:

- paper grain
- charcoal dust
- scratched wood
- dry ink
- faded cloth
- stained parchment

Rules:

- keep texture contrast below `12%`
- do not apply heavy noise to body text containers
- compress textures as WebP or AVIF
- use CSS overlays where possible
- preserve fast loading

---

## 23. Spacing Scale

```css
--space-1: 4px;
--space-2: 8px;
--space-3: 12px;
--space-4: 16px;
--space-5: 20px;
--space-6: 24px;
--space-8: 32px;
--space-10: 40px;
--space-12: 48px;
```

The layout should be denser than a modern marketing website.

Use:

- small gaps inside navigation panels
- moderate padding inside reading panels
- large separation only between major page regions

---

## 24. Motion

Motion should feel handmade and restrained.

Allowed:

- subtle wobble
- tiny rotation
- paper lift
- ink underline reveal
- short fade
- slight icon bounce
- frame-by-frame flicker for special decorations

Avoid:

- large spring animations
- excessive parallax
- constant moving backgrounds
- glossy 3D effects
- long animation durations

Respect:

```css
@media (prefers-reduced-motion: reduce) {
  * {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

---

## 25. Accessibility

Atmosphere must not reduce usability.

Requirements:

- body text contrast ratio at least `4.5:1`
- large text contrast at least `3:1`
- visible focus indicator
- keyboard-operable navigation
- alt text for informational images
- decorative imagery uses empty alt text
- tooltips are not the only way to expose information
- minimum interactive target size around `40px`
- content remains readable with textures disabled

---

## 26. Asset Direction

All assets must be original.

Create:

- dark survival objects
- rough crafting icons
- crooked trees
- tools
- food items
- creature silhouettes
- parchment scraps
- wooden panel frames
- candle or campfire motifs
- hand-inked ornaments

Illustration characteristics:

- black ink outlines
- cross-hatching
- exaggerated proportions
- imperfect circles and edges
- muted earth colors
- strong silhouettes
- slightly eerie expressions
- limited soft shading

Do not recreate identifiable characters, creatures, logos, maps, or interface assets from existing games.

---

## 27. Component Inventory

Build the following reusable components:

- `WikiHeader`
- `WikiLogo`
- `SearchBar`
- `LeftSidebar`
- `SidebarSection`
- `SidebarLink`
- `ContentShell`
- `PageTabs`
- `ActionTabs`
- `WelcomePanel`
- `HeroCarousel`
- `FeatureCard`
- `RightSidebar`
- `WidgetPanel`
- `CraftingGrid`
- `CraftingIcon`
- `ArticleCard`
- `Infobox`
- `StatsRow`
- `WikiTable`
- `Pagination`
- `Tooltip`
- `NoticeBox`
- `Footer`

---

## 28. Recommended CSS Tokens

```css
:root {
  --page-bg: #0d0b09;
  --page-bg-elevated: #14110e;
  --panel-bg: #1b1612;
  --panel-bg-soft: #251d17;
  --panel-bg-hover: #30251c;

  --parchment-light: #c8ad82;
  --parchment: #aa8963;
  --parchment-dark: #806248;

  --wood-light: #76563d;
  --wood: #4b3427;
  --wood-dark: #241913;

  --text-primary: #eee8dc;
  --text-secondary: #c8bbab;
  --text-muted: #8f8171;
  --text-dark: #1b140f;

  --link: #b89a3f;
  --link-hover: #dbc477;

  --accent-gold: #a98b35;
  --accent-rust: #87462e;
  --accent-blood: #712821;
  --accent-moss: #596044;
  --accent-bone: #d8ceb6;

  --border-dark: #17100c;
  --border-mid: #4e392a;
  --border-light: #806246;

  --shadow-deep: 0 8px 24px rgba(0, 0, 0, 0.5);
  --shadow-inset: inset 0 0 24px rgba(0, 0, 0, 0.45);

  --radius-none: 0;
  --radius-small: 2px;

  --duration-fast: 120ms;
  --duration-normal: 180ms;
}
```

---

## 29. Example Page Composition

```text
WikiHeader
├── WikiLogo
└── SearchBar

WikiLayout
├── LeftSidebar
│   ├── SidebarSection: Navigation
│   ├── SidebarSection: Portals
│   ├── SidebarSection: Tools
│   └── SidebarSection: Languages
│
├── ContentShell
│   ├── PageTabs
│   ├── ActionTabs
│   ├── WelcomePanel
│   ├── HeroCarousel
│   ├── FeaturedArticleGrid
│   └── RecentUpdates
│
└── RightSidebar
    ├── WidgetPanel: Latest Video
    ├── WidgetPanel: Crafting
    ├── WidgetPanel: Featured Guide
    └── WidgetPanel: Community
```

---

## 30. AI Implementation Prompt

When generating the site, use the following instruction:

```text
Build a standalone dark survival-game wiki interface from this DESIGN.md.

Do not imitate the generic wiki.gg platform layout mechanically.
Focus on the custom visual layer: dark handmade panels, aged parchment,
rough wood frames, distressed typography, original crafting icons,
dense encyclopedia content, and an atmospheric three-column layout.

Do not copy any copyrighted logo, character, illustration, icon, texture,
or exact UI asset from an existing game. Generate original placeholders
and original decorative assets in the same broad survival-fantasy genre.

Prioritize accessibility, responsive behavior, reusable components,
semantic HTML, and maintainable design tokens.
```
