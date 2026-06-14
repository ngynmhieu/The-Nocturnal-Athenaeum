# Styling Guidelines

> Visual conventions for The Nocturnal Athenaeum UI.
> All colors must be referenced via CSS variables defined in `src/index.css` — never raw hex/rgb values.
> Read `frontend_guidelines.md` rule 8 for the full color rule.

---

## Text color

Default body text for UI elements (labels, names, descriptions):

```
text-[var(--owl-brown)]
```

For stronger emphasis (headings, active labels, primary values):

```
text-[var(--owl-brown-deep)]
```

For secondary / muted text (emails, subtitles, hints):

```
text-[var(--owl-brown-muted)]
```

---

## Hover effect

Applied to any interactive element (buttons, nav items, menu rows):

```
hover:bg-[var(--owl-brown)]/10 hover:text-[var(--owl-brown-deep)] hover:font-medium backdrop-blur-sm transition-colors
```

- `bg-[var(--owl-brown)]/10` — subtle warm tint on hover
- `text-[var(--owl-brown-deep)]` — text darkens slightly to signal interactivity
- `font-medium` — weight bump reinforces the active state
- `backdrop-blur-sm` — softens the background behind the element
- `transition-colors` — smooth color transition (always pair with hover effects)

---

## Dropdown menu

Panel that appears below a trigger button (e.g. UserMenu):

```
absolute right-0 top-full mt-1
w-48 rounded-lg
border border-[var(--owl-brown)]/20
bg-[var(--background)] shadow-md
py-1 z-50
```

### Dropdown section divider

Between the header info block and action items:

```
border-b border-[var(--owl-brown)]/10
```

### Dropdown info block (non-interactive header row)

```
px-3 py-2
```

### Dropdown action row (interactive item inside the panel)

Combine with the hover effect above:

```
flex items-center gap-2 w-full
px-3 py-2
text-xs text-[var(--owl-brown)]
hover:bg-[var(--owl-brown)]/10 hover:text-[var(--owl-brown-deep)] hover:font-medium
backdrop-blur-sm transition-colors
```
