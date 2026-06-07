# Frontend Guideline Plan

This frontend should use a hybrid structure:

- **Modular monolith** for top-level business boundaries.
- **Feature-Sliced Design (FSD)** inside each module to organize UI and logic.

The goal is to keep the app easy to grow, easy to test, and easy to assign to teams without turning the codebase into a flat component dump.

## Core Rules

1. **Pages compose, they do not own everything.**
   - A page should assemble widgets and features.
   - It should not contain all business logic.

2. **Features contain user actions and workflows.**
   - Examples: login, search, add-to-cart, submit-order.
   - A feature can coordinate state, validation, and API calls for one action.

3. **Entities contain business concepts.**
   - Examples: user, product, order, invoice.
   - Keep domain types, mappers, selectors, and small entity-specific helpers here.

4. **Shared contains only reusable cross-cutting code.**
   - UI primitives, API client, utilities, constants, hooks, and configuration.
   - Shared code must not depend on business modules.

5. **Modules are business boundaries.**
   - Example modules: auth, catalog, orders, billing, analytics.
   - Modules should be isolated and expose only public APIs.

6. **UI and logic are separated.**
   - UI components should focus on rendering.
   - Logic should live in features, entities, or services.

7. **Cross-module imports should be limited.**
   - Import from another module only through its public API.
   - Avoid deep imports into internal folders.

8. **All colors must be defined in `index.css` and reused via CSS variables.**
   - Never use raw color codes (hex, rgb, oklch) directly in components.
   - Define all colors as CSS variables in `index.css` (e.g. `--color-primary: #7B3F1E`).
   - In components, reference them via Tailwind's arbitrary property syntax or CSS: `text-[var(--color-primary)]`.
   - If a new color is needed, add it to `index.css` first, then reuse the variable.

10. **Use proportional units only — never fixed pixel values.**
   - Use `rem`, `em`, `%`, `vw`, `vh`, `svh`, `fr`, or Tailwind's spacing scale (which is rem-based) for all sizing.
   - Never use `px` for widths, heights, margins, paddings, font sizes, or positions.
   - Exception: borders and outlines (`border-2`, `border`) may use `px` as they are decorative and do not affect layout flow.
   - This ensures the UI scales correctly across screen sizes and respects user font preferences.

9. **Imports must go through the module's public API, not deep into its folder.**
   - Every folder that exposes components must have an `index.ts` that re-exports them.
   - Consumers import from the folder level, not the file level.
   - Correct: `import { GradientBackground } from "@/shared/ui"`
   - Incorrect: `import { GradientBackground } from "@/shared/ui/GradientBackground"`

## Recommended Folder Structure

```txt
frontend/src/
  app/
    providers/
    router/
    styles/
  shared/
    api/
    ui/
    lib/
    config/
    assets/
  modules/
    auth/
      pages/
      widgets/
      features/
      entities/
      shared/
    catalog/
      pages/
      widgets/
      features/
      entities/
      shared/
    orders/
      pages/
      widgets/
      features/
      entities/
      shared/
```

## Folder Responsibilities

### `app/`
This is the application shell.

Main activities:
- Bootstrap providers
- Configure routing
- Register global styles
- Initialize app-wide state or theme
- Wire global error boundaries and layout wrappers

Use `app/` for things that must exist before the rest of the UI works.

### `shared/`
This is the global reusable layer.

Main activities:
- Design system components like button, input, modal, table
- Shared API client and request helpers
- Utility functions and constants
- Global configuration and environment access
- Generic hooks that are not business-specific
- Common assets such as icons or logos

Use `shared/` only for code that is truly reusable across the whole app.

### `modules/`
This is where business domains live.

Each module is a self-contained area of the product.

Main activities:
- Hold domain-specific UI and logic
- Keep feature-specific data flow contained
- Expose a clean public API to the rest of the app
- Prevent unrelated code from reaching inside the module

Example modules:
- `auth` for sign in, sign up, session handling
- `catalog` for listing, filtering, and viewing products
- `orders` for checkout, order history, and order details
- `billing` for payment and invoices
- `analytics` for charts, reports, and dashboards

### `pages/` inside a module
This is the route-level composition area inside a module.

Main activities:
- Assemble widgets and features into a screen
- Connect page data requirements to child blocks
- Keep route-specific composition, not deep business logic

Example:
- `orders/pages/order-details`
- `catalog/pages/catalog-home`

### `widgets/` inside a module
These are medium-to-large UI blocks built from smaller pieces.

Main activities:
- Combine multiple features and entities into one section of a screen
- Reuse on more than one page when possible
- Keep layout and screen composition manageable

A widget that grows complex enough to have its own private sub-components should become a folder with a `components/` subfolder:

```txt
widgets/
  ChatTranscript/
    index.ts              ← public API, only export exposed here
    ChatTranscript.tsx    ← the widget itself
    components/
      ChatMessage.tsx     ← private, only used by ChatTranscript
      TypingIndicator.tsx
      ScrollToBottom.tsx
```

- `components/` inside a widget is private — nothing outside the widget folder should import from it directly.
- The widget's `index.ts` is the only public entry point.
- Simple widgets with no sub-components remain as a single file (no folder needed).

Example:
- `orders/widgets/order-summary`
- `catalog/widgets/product-grid`

### `features/` inside a module
These are user-facing actions or workflows.

Main activities:
- Handle one business action
- Coordinate forms, validation, state, and API calls
- Emit events or callbacks to the surrounding UI

Example:
- `auth/features/login`
- `orders/features/cancel-order`
- `catalog/features/add-to-cart`

### `entities/` inside a module
These define the business objects and their local behavior.

Main activities:
- Store entity types and models
- Keep domain rules close to the concept
- Provide entity-specific selectors, formatters, and adapters
- Expose simple helpers that other layers can consume

Example:
- `orders/entities/order`
- `catalog/entities/product`
- `auth/entities/user`

### `shared/` inside a module
Use this only for code that is reusable within that module but not meant for the whole app.

Main activities:
- Module-specific helpers
- Module-specific UI fragments
- Small reusable utilities that support that module only

If something becomes useful across multiple modules, move it to root `shared/`.

## Dependency Rules

- `app` can depend on `shared` and modules.
- Modules can depend on `shared`.
- A module should avoid importing the private internals of another module.
- If another module needs something, expose it through a public API file.
- UI primitives should not import business logic.
- Business logic should not depend on page composition.

## Practical Division of Responsibility

### UI layer
Handles:
- Rendering
- Styling
- Layout
- Basic interaction feedback
- Passing events upward

Should not handle:
- Complex business decisions
- Cross-module workflows
- Server orchestration logic

### Logic layer
Handles:
- Validation
- API requests
- Workflow state
- Business rules
- Data transformation

Should not handle:
- Page layout decisions
- Styling details
- Presentational concerns

## Example Flow

For an order details screen:

- `pages/order-details` loads the screen.
- `widgets/order-header` shows the top summary.
- `entities/order` provides the order model and formatting.
- `features/cancel-order` handles the cancel action.
- `shared/ui/button` provides the button component.

This keeps the screen clear and keeps logic in the right place.

## When to Move Code

Move code to a more specific folder when:
- A component is used only inside one business area.
- A function starts carrying domain rules.
- A shared utility starts depending on business data.
- A page becomes too large and starts mixing concerns.

## What Success Looks Like

A good frontend architecture should let you answer these questions quickly:
- Which business module owns this code?
- Is this UI or logic?
- Is this reusable across the app or only inside one module?
- Can another developer find the right file without guessing?

If the answer is clear, the structure is working.
