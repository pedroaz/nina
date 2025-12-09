# Technology Stack

This document defines the specific technologies and versions used in the Nina repository. Agents must adhere to these versions to avoid compatibility issues.

## Web App (`packages/web-app`)
- **Framework**: Next.js 15.5.6 (App Router)
- **Language**: TypeScript
- **UI Library**: React 18.3.1
- **Styling**: Tailwind CSS 4
- **Components**: Radix UI (shadcn/ui compatible)
- **State Management**: Zustand
- **Validation**: Zod
- **Icons**: Lucide React

## Landing Page (`packages/landing-page`)
- **Framework**: Next.js 14.2.5 (App Router)
- **Language**: TypeScript
- **UI Library**: React 18
- **Styling**: Tailwind CSS 3.4.1
- **Animations**: Framer Motion
- **Carousel**: Embla Carousel

## Core (`packages/core`)
- **AI Framework**: Genkit
- **Database**: MongoDB with Mongoose
- **Validation**: Zod

## General
- **Package Manager**: pnpm
- **Runtime**: Node.js
