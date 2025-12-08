# Web App Style Guide

This document outlines the design system and styling guidelines for the Nina Web App (`packages/web-app`).

## Design Philosophy

The Nina Web App features a **playful, engaging design** inspired by language learning apps like Duolingo. Key characteristics include:
- **Rounded Corners**: Generous border radius (`rounded-2xl`, `rounded-3xl`).
- **Bold Borders**: Thick, dark borders (`border-[3px]`, `border-neutral-900`).
- **Vibrant Colors**: Primary Orange (`orange-500`), Secondary Teal (`teal-500`), and clear semantic colors (Success Green, Error Red).
- **Tactile Feel**: Buttons and cards have "depth" via borders and shadows, with active states that simulate pressing.

## Core Components

We have standardized the core UI components to automatically apply this playful style. **Always use these components** instead of raw HTML or utility classes.

### 1. Card (`components/ui/card.tsx`)
The default `Card` component applies the `card-playful` style: white background, thick border, shadow, and hover lift effect.

```tsx
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";

<Card>
  <CardHeader>
    <CardTitle>My Deck</CardTitle>
  </CardHeader>
  <CardContent>
    Content goes here...
  </CardContent>
</Card>
```

### 2. Button (`components/ui/button.tsx`)
Buttons are styled to be chunky and clickable.

- **Default (Primary)**: Orange. Use for main actions.
- **Secondary**: Teal. Use for alternative actions.
- **Destructive**: Red. Use for delete/dangerous actions.
- **Outline**: White with dark border. Use for secondary/tertiary actions.

```tsx
import { Button } from "@/components/ui/button";

<Button>Primary Action</Button>
<Button variant="secondary">Secondary Action</Button>
<Button variant="destructive">Delete</Button>
<Button variant="outline">Cancel</Button>
```

### 3. Badge (`components/ui/badge.tsx`)
Badges are used for labels, counts, and status.

- **Default**: Primary color.
- **Teal**: `variant="teal"`.
- **Orange**: `variant="orange"`.

```tsx
import { Badge } from "@/components/ui/badge";

<Badge variant="teal">10 Cards</Badge>
```

### 4. Progress (`components/ui/progress.tsx`)
The progress bar has a thick border and distinct fill.

```tsx
import { Progress } from "@/components/ui/progress";

<Progress value={50} />
```

## Icons

**ALWAYS use [Lucide React](https://lucide.dev/icons/) icons.**
Do not use emojis for UI elements.

**Prefer icons over text for common actions.**
If an action is universally understood (like "Delete", "Edit", "Close"), use the icon alone or with a tooltip to save space and reduce visual clutter.

```tsx
import { Trash2 } from "lucide-react";

{/* Preferred: Icon only for common actions */}
<Button variant="destructive" size="icon">
  <Trash2 className="size-4" />
</Button>

{/* Acceptable: Icon + Text for clarity if needed */}
<Button variant="destructive">
  <Trash2 className="mr-2 size-4" /> Delete
</Button>
```

## Styling & CSS

- **Global Styles**: The core "playful" utility classes (`.card-playful`, `.btn-playful`, etc.) are defined in `app/globals.css`.
- **Tailwind CSS**: Use Tailwind utility classes for layout (flex, grid, spacing).
- **Colors**: Use the semantic color variables defined in `globals.css` (e.g., `bg-orange-50`, `text-neutral-900`).

## Creating New Components

When creating new components:
1.  **Reuse**: Check if a standard component (`Card`, `Button`) can be used.
2.  **Consistency**: If you need a custom element, try to use the `card-playful` or `btn-playful` utility classes (or better yet, the components that wrap them) to maintain consistency.
3.  **Lucide**: Use Lucide icons.

## Do's and Don'ts

- **DO** use `<Card>` for containers.
- **DO** use `<Button>` for interactive elements.
- **DON'T** create new card styles unless absolutely necessary.
- **DON'T** use emojis in buttons or labels (use icons).
- **DON'T** override the global styles locally unless for specific layout needs.
