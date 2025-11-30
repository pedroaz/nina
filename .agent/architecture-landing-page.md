# Landing Page Architecture

The `landing-page` package is the public face of Nina, designed to showcase the product and convert visitors.

## Tech Stack
- **Framework**: Next.js 14
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **Animations**: Framer Motion, Tailwindcss Animate
- **UI Components**: Radix UI primitives
- **Carousel**: Embla Carousel

## Directory Structure (`packages/landing-page`)

- **`app/`**: Contains the application routes and pages (App Router).
- **`components/`**: UI components specific to the landing page.
- **`data/`**: Static data files (likely for content).
- **`lib/`**: Utility functions.
- **`public/`**: Static assets.

## Key Patterns
- **Static Site Generation (SSG)**: Likely used for optimal performance and SEO, given the nature of a landing page.
- **Component-Based Design**: Reusable components for sections like Hero, Features, Testimonials, etc.

## Integration
- Operates independently but links to the `web-app`.
